"""
Testes de Integração – Pipeline LangGraph Multi-Agente completo (end-to-end)
Usa ChromaDB in-memory, fakeredis e MockLLMService: executa sem nenhuma API externa.
"""
import pytest
from src.workflow.graph import create_audit_graph
from src.workflow.state import AuditState
from src.config.settings import settings


SAMPLE_CONTRACT = """CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE TI

CLÁUSULA PRIMEIRA – DO OBJETO
1.1. Prestação de serviços de computação em nuvem e suporte técnico.

CLÁUSULA SEGUNDA – DAS PENALIDADES E MULTAS
2.1. Multa rescisória de 30% sobre o valor remanescente.
2.2. Retenção cautelar de até 100% dos pagamentos sem contraditório.

CLÁUSULA TERCEIRA – DA RESCISÃO UNILATERAL
3.1. A Contratante poderá rescindir com aviso prévio de 5 dias sem indenização.

CLÁUSULA QUARTA – DA RESPONSABILIDADE CIVIL
4.1. A Contratada responde ilimitadamente por danos diretos e lucros cessantes.

CLÁUSULA QUINTA – DADOS E LGPD
5.1. Os dados pessoais deverão ser protegidos conforme LGPD.
5.2. O prazo para comunicar incidentes é de 60 dias úteis.
"""


def get_initial_state(session_id: str = "int-test-001") -> AuditState:
    return AuditState(
        session_id=session_id,
        document_name="contrato_integracao.txt",
        raw_bytes=SAMPLE_CONTRACT.encode("utf-8"),
        raw_text="",
        chunks=[],
        rag_results=[],
        compliance_report=None,
        auditor_critique=None,
        revision_count=0,
        max_revisions=settings.MAX_AUDIT_REVISIONS,
        status="pending",
        agent_logs=[],
        final_report=None,
    )


def test_full_pipeline_runs_to_completion():
    """Pipeline completo deve gerar um ConsolidatedAuditReport final."""
    events = []

    def on_event(session_id, agent, progress, msg, payload):
        events.append({"agent": agent, "progress": progress, "message": msg})

    graph = create_audit_graph(event_callback=on_event)
    final_state = graph.invoke(get_initial_state())

    assert final_state["status"] == "completed"
    assert final_state["final_report"] is not None
    assert len(final_state["chunks"]) > 0
    assert len(final_state["rag_results"]) > 0
    assert final_state["compliance_report"] is not None
    assert final_state["auditor_critique"] is not None


def test_pipeline_agent_logs_are_generated():
    """Todos os agentes devem registrar ao menos uma entrada no log."""
    graph = create_audit_graph()
    final_state = graph.invoke(get_initial_state("log-test-002"))
    logs = final_state["agent_logs"]
    agents_logged = {log["agent"] for log in logs}
    assert "extractor" in agents_logged
    assert "researcher" in agents_logged
    assert "compliance" in agents_logged
    assert "auditor" in agents_logged


def test_pipeline_no_infinite_loop():
    """Revisões do auditor devem ser limitadas pelo MAX_AUDIT_REVISIONS."""
    graph = create_audit_graph()
    state = get_initial_state("loop-test-003")
    state["max_revisions"] = 2
    final_state = graph.invoke(state)
    assert final_state["revision_count"] <= 2 + 1  # +1 para a última rodada que aprova


def test_pipeline_final_report_fields():
    """O relatório final deve ter todos os campos obrigatórios preenchidos."""
    graph = create_audit_graph()
    final_state = graph.invoke(get_initial_state("fields-test-004"))
    report = final_state["final_report"]

    assert report.session_id == "fields-test-004"
    assert report.document_name == "contrato_integracao.txt"
    assert report.final_verdict != ""
    assert 0 <= report.overall_risk_score <= 100
    assert 0 <= report.audit_quality_score <= 100
    assert len(report.recommendations) >= 1
    assert len(report.compliance_findings) >= 1


def test_pipeline_event_callbacks_received():
    """Verificar que callbacks WebSocket foram disparados ao longo do pipeline."""
    events = []

    def on_event(session_id, agent, progress, msg, payload):
        events.append(agent)

    graph = create_audit_graph(event_callback=on_event)
    graph.invoke(get_initial_state("events-test-005"))

    assert "extractor" in events
    assert "researcher" in events
    assert "compliance" in events
    assert "auditor" in events


def test_pipeline_with_empty_document():
    """Pipeline não deve travar com documento vazio — deve completar com relatório padrão."""
    graph = create_audit_graph()
    state = get_initial_state("empty-test-006")
    state["raw_bytes"] = b""
    state["document_name"] = "vazio.txt"
    final_state = graph.invoke(state)
    assert final_state["status"] == "completed"
    assert final_state["final_report"] is not None
