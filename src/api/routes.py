"""
Rotas REST da API FastAPI para o Sistema Multi-Agente Corporativo
"""
import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Response
from fastapi.responses import PlainTextResponse

from src.workflow.state import AuditState
from src.workflow.graph import create_audit_graph
from src.api.websocket import dispatch_event_sync
from src.services.cache_service import semantic_cache
from src.services.vector_service import vector_service
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# Armazenamento em memória das sessões ativas
sessions_store: Dict[str, Dict[str, Any]] = {}

SAMPLE_CORPORATE_CONTRACT = """INSTRUMENTO PARTICULAR DE PRESTAÇÃO DE SERVIÇOS DE TECNOLOGIA DA INFORMAÇÃO E PROCESSAMENTO EM NUVEM

DAS PARTES:
CONTRATANTE: MEGA CORP PARTICIPAÇÕES S.A., inscrita no CNPJ sob nº 11.222.333/0001-44.
CONTRATADA: TECH SOLUTIONS SERVIÇOS DE SOFTWARE LTDA., inscrita no CNPJ sob nº 55.666.777/0001-88.

CLÁUSULA PRIMEIRA – DO OBJETO
1.1. O presente instrumento tem por objeto a prestação contínua de serviços de computação em nuvem, migração de dados e suporte técnico especializado pela Contratada à Contratante.

CLÁUSULA SEGUNDA – DOS VALORES E REMUNERAÇÃO
2.1. Pelos serviços prestados, a Contratante pagará o valor fixo mensal de R$ 150.000,00 (cento e cinquenta mil reais).
2.2. Os valores acordados permanecerão fixos e irreajustáveis durante toda a vigência do contrato, vedado qualquer reajuste inflacionário mesmo após 12 (doze) meses de vigência.

CLÁUSULA TERCEIRA – DAS PENALIDADES E RETENÇÃO DE CRÉDITOS
3.1. Em caso de atraso injustificado superior a 24 (vinte e quatro) horas na entrega de qualquer módulo de software, será aplicada multa rescisória de 30% sobre o valor remanescente do contrato.
3.2. Fica autorizada à Contratante a retenção cautelar de até 100% dos pagamentos em processamento por serviços já executados, a título de garantia de eventuais perdas futuras, sem necessidade de notificação prévia ou contraditório.

CLÁUSULA QUARTA – DA RESCISÃO CONTRATUAL
4.1. A Contratante poderá rescindir unilateralmente este ajuste a qualquer tempo com aviso prévio de 5 (cinco) dias, sem que lhe seja imputada qualquer penalidade, indenização ou pagamento de investimentos não amortizados da Contratada.
4.2. Caso a Contratada deseje rescindir o contrato, deverá conceder aviso prévio mínimo de 180 (cento e oitenta) dias, sob pena de multa equivalente a 12 (doze) mensalidades integrais.

CLÁUSULA QUINTA – DA RESPONSABILIDADE CIVIL
5.1. A Contratada responderá ilimitadamente por todos os danos diretos, indiretos, morais e lucros cessantes decorrentes do contrato, inclusive decorrentes de indisponibilidade de terceiros provedores de telecomunicações.
5.2. A responsabilidade da Contratante perante a Contratada limita-se estritamente ao valor de 1 (uma) mensalidade.

CLÁUSULA SEXTA – DA PRIVACIDADE E DADOS (LGPD)
6.1. O fornecedor deverá manter em sigilo todos os dados compartilhados, respondendo regressivamente por quaisquer vazamentos ocorridos na infraestrutura contratada.
6.2. Não haverá obrigação de notificação tempestiva de incidentes pelo Operador antes de 30 (trinta) dias úteis da identificação do evento.

CLÁUSULA SÉTIMA – DO FORO
7.1. Fica eleito o Foro da Comarca de São Paulo/SP com renúncia expressa a qualquer outro.
"""


def run_audit_workflow_task(session_id: str):
    """Executa o grafo multi-agente de forma síncrona/assíncrona no background."""
    session_data = sessions_store.get(session_id)
    if not session_data:
        return

    session_data["status"] = "processing"

    def callback(s_id, agent_name, progress, message, payload):
        dispatch_event_sync(s_id, agent_name, progress, message, payload)
        if s_id in sessions_store:
            sessions_store[s_id]["progress"] = progress
            sessions_store[s_id]["current_message"] = message
            sessions_store[s_id]["current_agent"] = agent_name

    graph = create_audit_graph(event_callback=callback)

    initial_state: AuditState = {
        "session_id": session_id,
        "document_name": session_data["document_name"],
        "raw_bytes": session_data["raw_bytes"],
        "raw_text": "",
        "chunks": [],
        "rag_results": [],
        "compliance_report": None,
        "auditor_critique": None,
        "revision_count": 0,
        "max_revisions": settings.MAX_AUDIT_REVISIONS,
        "status": "pending",
        "agent_logs": [],
        "final_report": None
    }

    try:
        final_state = graph.invoke(initial_state)
        session_data["status"] = "completed"
        session_data["progress"] = 100
        session_data["state"] = final_state
        session_data["final_report"] = final_state.get("final_report")
    except Exception as e:
        logger.error(f"Erro na execução do grafo de auditoria para sessão {session_id}: {e}", exc_info=True)
        session_data["status"] = "error"
        session_data["error"] = str(e)
        dispatch_event_sync(session_id, "orchestrator", 100, f"Erro na auditoria: {e}", {"error": str(e)})


@router.get("/health")
def health_check():
    """Checagem de integridade dos serviços integrados."""
    cache_stats = semantic_cache.get_stats()
    chroma_count = vector_service.count()
    return {
        "status": "healthy",
        "llm_provider": settings.LLM_PROVIDER,
        "cache": cache_stats,
        "chromadb_chunks_indexed": chroma_count,
        "max_audit_revisions": settings.MAX_AUDIT_REVISIONS
    }


@router.post("/audit/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auto_start: bool = Form(default=True)
):
    """Realiza upload de arquivo (PDF, TXT, MD) e inicializa sessão de auditoria."""
    content = await file.read()
    session_id = str(uuid.uuid4())

    sessions_store[session_id] = {
        "session_id": session_id,
        "document_name": file.filename,
        "raw_bytes": content,
        "file_size": len(content),
        "status": "uploaded",
        "progress": 0,
        "current_message": "Documento carregado no servidor.",
        "current_agent": "extractor",
        "state": None,
        "final_report": None
    }

    if auto_start and background_tasks:
        background_tasks.add_task(run_audit_workflow_task, session_id)
        sessions_store[session_id]["status"] = "processing"

    return {
        "session_id": session_id,
        "document_name": file.filename,
        "size_bytes": len(content),
        "status": sessions_store[session_id]["status"]
    }


@router.post("/audit/sample")
def load_sample_and_start(background_tasks: BackgroundTasks):
    """Cria uma sessão com um contrato corporativo de teste com cláusulas de alto risco."""
    session_id = str(uuid.uuid4())
    doc_name = "Minuta_Contrato_TI_MegaCorp.txt"
    content = SAMPLE_CORPORATE_CONTRACT.encode("utf-8")

    sessions_store[session_id] = {
        "session_id": session_id,
        "document_name": doc_name,
        "raw_bytes": content,
        "file_size": len(content),
        "status": "processing",
        "progress": 5,
        "current_message": "Iniciando processamento do contrato de demonstração...",
        "current_agent": "extractor",
        "state": None,
        "final_report": None
    }

    background_tasks.add_task(run_audit_workflow_task, session_id)

    return {
        "session_id": session_id,
        "document_name": doc_name,
        "message": "Contrato de demonstração carregado com sucesso. Auditoria em andamento."
    }


@router.post("/audit/{session_id}/start")
def start_audit_manually(session_id: str, background_tasks: BackgroundTasks):
    """Inicia manualmente a auditoria para uma sessão previamente carregada."""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    sessions_store[session_id]["status"] = "processing"
    background_tasks.add_task(run_audit_workflow_task, session_id)
    return {"session_id": session_id, "status": "processing"}


@router.get("/audit/{session_id}/status")
def get_audit_status(session_id: str):
    """Retorna o estado e progresso atual da auditoria."""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    sess = sessions_store[session_id]
    state = sess.get("state")

    findings = []
    if state and state.get("compliance_report"):
        findings = [f.model_dump() for f in state["compliance_report"].findings]

    return {
        "session_id": session_id,
        "document_name": sess.get("document_name"),
        "status": sess.get("status"),
        "progress": sess.get("progress", 0),
        "current_message": sess.get("current_message"),
        "current_agent": sess.get("current_agent"),
        "revision_count": state.get("revision_count", 0) if state else 0,
        "findings_count": len(findings),
        "findings": findings,
        "has_final_report": sess.get("final_report") is not None
    }


@router.get("/audit/{session_id}/report")
def get_audit_report(session_id: str):
    """Retorna o parecer final estruturado da auditoria."""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    sess = sessions_store[session_id]
    final_report = sess.get("final_report")

    if not final_report:
        if sess.get("status") == "processing":
            return {"status": "processing", "message": "Auditoria ainda em andamento."}
        raise HTTPException(status_code=400, detail="Relatório ainda não gerado ou com erro.")

    return final_report.model_dump()


@router.get("/audit/{session_id}/markdown", response_class=PlainTextResponse)
def get_audit_report_markdown(session_id: str):
    """Exporta o parecer final formatado em Markdown executivo para download."""
    if session_id not in sessions_store:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    sess = sessions_store[session_id]
    final_report = sess.get("final_report")

    if not final_report:
        raise HTTPException(status_code=400, detail="Relatório final não disponível.")

    lines = [
        f"# 📋 PARECER EXECUTIVO DE AUDITORIA MULTI-AGENTE",
        f"**Documento Auditado:** {final_report.document_name}",
        f"**Sessão:** `{final_report.session_id}`",
        f"**Data da Auditoria:** {final_report.audit_timestamp.strftime('%d/%m/%Y %H:%M:%S')} UTC",
        f"**Veredito:** `{final_report.final_verdict}`",
        f"**Score de Risco Global:** {final_report.overall_risk_score}/100",
        f"**Nota de Integridade do Auditor:** {final_report.audit_quality_score}/100",
        f"**Ciclos de Revisão Executados:** {final_report.total_revisions_executed}",
        "",
        "## 1. RESUMO EXECUTIVO",
        final_report.executive_summary,
        "",
        "## 2. APONTAMENTOS DE COMPLIANCE E RISCOS IDENTIFICADOS",
    ]

    for idx, f in enumerate(final_report.compliance_findings, 1):
        lines.append(f"### {idx}. [{f.risk_level.value.upper()}] {f.clause_title}")
        lines.append(f"- **Fundamentação Legal:** {f.legal_basis}")
        lines.append(f"- **Página:** {f.page_number}")
        lines.append(f"- **Trecho Contratual:** > *\"{f.offending_text}\"*")
        lines.append(f"- **Descrição do Risco:** {f.risk_description}")
        lines.append(f"- **Recomendação Mitigatória:** {f.mitigation_recommendation}")
        lines.append("")

    lines.append("## 3. NOTAS E PARECER DO AUDITOR REVISOR")
    lines.append(final_report.auditor_comments)
    lines.append("")
    lines.append("## 4. RECOMENDAÇÕES PRIORITÁRIAS")
    for r in final_report.recommendations:
        lines.append(f"- {r}")

    return "\n".join(lines)


@router.get("/cache/stats")
def get_cache_stats():
    """Retorna estatísticas operacionais do cache semântico."""
    return semantic_cache.get_stats()


@router.post("/cache/clear")
def clear_cache():
    """Limpa o cache semântico."""
    semantic_cache.clear()
    return {"message": "Cache semântico limpo com sucesso."}
