"""
Testes do Agente 3 (Compliance/Jurídico) e do Agente 4 (Auditor Revisor)
"""
import pytest
from src.agents.compliance import ComplianceAgent
from src.agents.auditor import AuditorAgent
from src.schemas.models import (
    RAGSearchResult, ComplianceReport, ComplianceFinding,
    DocumentChunk, RiskLevel, AuditCritique
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_rag_results() -> list[RAGSearchResult]:
    return [
        RAGSearchResult(
            chunk_id="chk_1",
            text="Multa rescisória de 30% sobre o valor remanescente e retenção cautelar de até 100% dos pagamentos.",
            page_number=1,
            section_name="Cláusula das Penalidades",
            similarity_score=0.92,
            rerank_score=0.88,
        ),
        RAGSearchResult(
            chunk_id="chk_2",
            text="A Contratante poderá rescindir unilateralmente em 5 dias sem indenizar.",
            page_number=2,
            section_name="Cláusula de Rescisão",
            similarity_score=0.87,
            rerank_score=0.83,
        ),
        RAGSearchResult(
            chunk_id="chk_3",
            text="A Contratada responde ilimitadamente por danos diretos, indiretos e lucros cessantes.",
            page_number=1,
            section_name="Cláusula de Responsabilidade",
            similarity_score=0.80,
            rerank_score=0.77,
        ),
    ]


def make_chunks() -> list[DocumentChunk]:
    texts = [
        "Multa rescisória de 30% sobre o valor remanescente e retenção cautelar de até 100% dos pagamentos.",
        "A Contratante poderá rescindir unilateralmente em 5 dias.",
        "A Contratada responde ilimitadamente por danos diretos e lucros cessantes.",
    ]
    return [
        DocumentChunk(
            id=f"chk_{i+1}", text=t, document_name="doc.txt",
            page_number=i+1, chunk_index=i,
            token_estimate=len(t.split()),
            content_hash="a" * 64,
        )
        for i, t in enumerate(texts)
    ]


# ─── Compliance Agent Tests ──────────────────────────────────────────────────

def test_compliance_returns_report():
    agent = ComplianceAgent()
    rag = make_rag_results()
    report = agent.analyze_compliance("contrato_teste.txt", rag)

    assert isinstance(report, ComplianceReport)
    assert report.document_name == "contrato_teste.txt"
    assert isinstance(report.findings, list)
    assert len(report.findings) >= 1
    assert 0 <= report.overall_risk_score <= 100


def test_compliance_findings_have_required_fields():
    agent = ComplianceAgent()
    report = agent.analyze_compliance("teste.txt", make_rag_results())

    for f in report.findings:
        assert isinstance(f, ComplianceFinding)
        assert f.id
        assert f.clause_title
        assert f.risk_level in RiskLevel
        assert f.legal_basis
        assert f.mitigation_recommendation


def test_compliance_risk_counts_are_consistent():
    agent = ComplianceAgent()
    report = agent.analyze_compliance("teste.txt", make_rag_results())

    total_counted = (
        report.critical_count + report.high_count +
        report.medium_count + report.low_count
    )
    assert total_counted == len(report.findings)


def test_compliance_high_risk_text_raises_score():
    """Um contrato com cláusulas de multa, rescisão e LGPD deve ter score > 30."""
    agent = ComplianceAgent()
    report = agent.analyze_compliance("alto_risco.txt", make_rag_results())
    assert report.overall_risk_score > 30


def test_compliance_with_revision_instructions():
    """Passando instruções do auditor, a análise deve continuar funcionando."""
    agent = ComplianceAgent()
    report = agent.analyze_compliance(
        "revisado.txt",
        make_rag_results(),
        revision_instructions="Reforçar análise das cláusulas de limitação de responsabilidade."
    )
    assert isinstance(report, ComplianceReport)


# ─── Auditor Agent Tests ─────────────────────────────────────────────────────

def make_compliance_report(n_findings: int = 2) -> ComplianceReport:
    findings = [
        ComplianceFinding(
            id=f"FIND-{i:03d}",
            clause_title=f"Cláusula de Risco {i}",
            risk_level=RiskLevel.ALTO,
            risk_description="Risco identificado na cláusula.",
            legal_basis="Art. 412 do Código Civil.",
            offending_text="Multa rescisória de 30%",
            mitigation_recommendation="Reduzir multa para 10%.",
            page_number=1,
        )
        for i in range(n_findings)
    ]
    return ComplianceReport(
        document_name="doc.txt",
        overall_risk_score=50,
        high_count=n_findings,
        findings=findings,
        executive_summary="Auditoria preliminar com riscos relevantes.",
    )


def test_auditor_approves_below_max_revisions():
    agent = AuditorAgent()
    report = make_compliance_report()
    critique = agent.review_findings(
        document_name="doc.txt",
        chunks=make_chunks(),
        rag_results=make_rag_results(),
        compliance_report=report,
        current_revision=0,
        max_revisions=2,
    )
    assert isinstance(critique, AuditCritique)
    assert isinstance(critique.approved, bool)
    assert 0 <= critique.audit_score <= 100


def test_auditor_forces_approval_at_max_revisions():
    """Garante que ao atingir max_revisions, o auditor SEMPRE aprova (sem loop infinito)."""
    agent = AuditorAgent()
    report = make_compliance_report()
    critique = agent.review_findings(
        document_name="doc.txt",
        chunks=make_chunks(),
        rag_results=make_rag_results(),
        compliance_report=report,
        current_revision=2,
        max_revisions=2,
    )
    assert critique.approved is True


def test_auditor_consolidation_generates_report():
    agent = AuditorAgent()
    compliance_report = make_compliance_report(3)
    critique = AuditCritique(
        approved=True,
        audit_score=91,
        feedback_notes="Auditoria aprovada com ressalvas.",
    )
    final = agent.consolidate_final_report(
        session_id="sess-123",
        document_name="contrato.txt",
        compliance_report=compliance_report,
        critique=critique,
        revisions_count=1,
        agent_logs=[],
    )
    assert final.session_id == "sess-123"
    assert final.final_verdict != ""
    assert len(final.recommendations) >= 1
    assert final.audit_quality_score == 91


def test_auditor_verdict_critical_risk():
    """Se há achados críticos, o veredito deve mencionar risco crítico."""
    agent = AuditorAgent()
    report = make_compliance_report()
    report.critical_count = 2
    report.findings[0].risk_level = RiskLevel.CRITICO
    critique = AuditCritique(approved=True, audit_score=85, feedback_notes="OK")
    final = agent.consolidate_final_report("s1", "doc.txt", report, critique, 1, [])
    assert "CRÍTICO" in final.final_verdict.upper() or "RECOMENDADO" in final.final_verdict.upper()
