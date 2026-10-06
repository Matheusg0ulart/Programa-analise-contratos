"""
Orquestrador Multi-Agente com LangGraph
Gerencia o fluxo de trabalho cíclico com salvaguarda matemática contra loops infinitos.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from langgraph.graph import StateGraph, START, END

from src.workflow.state import AuditState
from src.agents.extractor import extractor_agent
from src.agents.researcher import researcher_agent
from src.agents.compliance import compliance_agent
from src.agents.auditor import auditor_agent
from src.config.settings import settings

logger = logging.getLogger(__name__)


def create_audit_graph(event_callback: Optional[Callable[[str, str, int, str, Dict[str, Any]], None]] = None):
    """
    Constrói e compila o StateGraph do LangGraph para auditoria multi-agente.
    event_callback: assinatura (session_id, agent_name, progress, message, payload)
    """

    def notify(session_id: str, agent_name: str, progress: int, message: str, payload: Dict[str, Any] = None):
        if event_callback:
            try:
                event_callback(session_id, agent_name, progress, message, payload or {})
            except Exception as e:
                logger.error(f"Erro no callback de evento: {e}")

    # =========================================================================
    # NÓ 1: Extrator Inteligente
    # =========================================================================
    def extractor_node(state: AuditState) -> Dict[str, Any]:
        session_id = state["session_id"]
        doc_name = state["document_name"]
        logger.info(f"==> [Nó 1] Iniciando Extrator para: {doc_name}")

        notify(session_id, "extractor", 10, "Iniciando leitura de documento e pré-processamento...")

        extraction = extractor_agent.process_document(
            file_bytes=state["raw_bytes"],
            filename=doc_name
        )

        notify(
            session_id, "extractor", 25,
            f"Extração concluída: {extraction.total_pages} página(s), {extraction.total_chunks} chunks semânticos.",
            {"total_pages": extraction.total_pages, "total_chunks": extraction.total_chunks, "ocr": extraction.ocr_applied}
        )

        log_entry = {
            "agent": "extractor",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "extraction_completed",
            "details": f"Gerados {extraction.total_chunks} chunks semânticos. OCR aplicado: {extraction.ocr_applied}."
        }

        return {
            "chunks": extraction.chunks,
            "raw_text": extraction.preview_text,
            "agent_logs": state["agent_logs"] + [log_entry],
            "status": "extracted"
        }

    # =========================================================================
    # NÓ 2: Pesquisador / RAG Avançado
    # =========================================================================
    def researcher_node(state: AuditState) -> Dict[str, Any]:
        session_id = state["session_id"]
        logger.info(f"==> [Nó 2] Iniciando Pesquisador / RAG para sessão: {session_id}")

        notify(session_id, "researcher", 35, "Indexando trechos no banco vetorial e consultando cache semântico...")

        # Indexa no banco vetorial
        researcher_agent.index_document_chunks(state["chunks"])

        notify(session_id, "researcher", 50, "Executando busca semântica multi-query e re-ranking híbrido...")

        # Executa pesquisa e reranking
        rag_results = researcher_agent.run_multi_query_audit()

        cached_hits = sum(1 for r in rag_results if r.is_cached)

        notify(
            session_id, "researcher", 60,
            f"RAG concluído: {len(rag_results)} trechos críticos ranqueados. Hits de Cache Semântico: {cached_hits}.",
            {"total_retrieved": len(rag_results), "cached_hits": cached_hits}
        )

        log_entry = {
            "agent": "researcher",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "rag_completed",
            "details": f"{len(rag_results)} trechos ranqueados com re-ranking híbrido. {cached_hits} obtidos via cache semântico."
        }

        return {
            "rag_results": rag_results,
            "agent_logs": state["agent_logs"] + [log_entry],
            "status": "researched"
        }

    # =========================================================================
    # NÓ 3: Jurídico & Compliance
    # =========================================================================
    def compliance_node(state: AuditState) -> Dict[str, Any]:
        session_id = state["session_id"]
        doc_name = state["document_name"]
        rev_count = state["revision_count"]
        critique = state.get("auditor_critique")
        rev_instructions = critique.instructions_for_revision if critique else None

        logger.info(f"==> [Nó 3] Iniciando Compliance (Rodada de análise: {rev_count + 1})")

        notify(
            session_id, "compliance", 70,
            f"Analisando cláusulas de risco e multas à luz da legislação (Ciclo {rev_count + 1})...",
            {"revision_round": rev_count + 1}
        )

        compliance_rep = compliance_agent.analyze_compliance(
            document_name=doc_name,
            rag_results=state["rag_results"],
            revision_instructions=rev_instructions
        )

        notify(
            session_id, "compliance", 80,
            f"Auditoria de risco concluída: Score {compliance_rep.overall_risk_score}/100. "
            f"{len(compliance_rep.findings)} cláusulas impugnadas.",
            {"risk_score": compliance_rep.overall_risk_score, "findings_count": len(compliance_rep.findings)}
        )

        log_entry = {
            "agent": "compliance",
            "timestamp": datetime.utcnow().isoformat(),
            "action": f"compliance_analysis_round_{rev_count + 1}",
            "details": f"Score {compliance_rep.overall_risk_score}/100. Achados: {len(compliance_rep.findings)}."
        }

        return {
            "compliance_report": compliance_rep,
            "agent_logs": state["agent_logs"] + [log_entry],
            "status": "compliance_analyzed"
        }

    # =========================================================================
    # NÓ 4: Auditor Revisor (Crítica e Fact-Checking)
    # =========================================================================
    def auditor_node(state: AuditState) -> Dict[str, Any]:
        session_id = state["session_id"]
        doc_name = state["document_name"]
        current_rev = state["revision_count"]
        max_rev = state["max_revisions"]

        logger.info(f"==> [Nó 4] Auditor Revisor checando apontamentos. Ciclo {current_rev + 1}/{max_rev}")

        notify(
            session_id, "auditor", 85,
            f"Auditor Revisor checando alucinações e validando coerência dos apontamentos...",
            {"cycle": current_rev + 1, "max_cycles": max_rev}
        )

        critique = auditor_agent.review_findings(
            document_name=doc_name,
            chunks=state["chunks"],
            rag_results=state["rag_results"],
            compliance_report=state["compliance_report"],
            current_revision=current_rev,
            max_revisions=max_rev
        )

        new_rev_count = current_rev + 1

        notify(
            session_id, "auditor", 90,
            f"Avaliação do Auditor: {'APROVADO' if critique.approved else 'REPROVADO / SOLICITADO AJUSTE'} "
            f"(Nota de Integridade: {critique.audit_score}/100).",
            {"approved": critique.approved, "audit_score": critique.audit_score, "cycle": new_rev_count}
        )

        log_entry = {
            "agent": "auditor",
            "timestamp": datetime.utcnow().isoformat(),
            "action": f"audit_review_cycle_{new_rev_count}",
            "details": f"Aprovado: {critique.approved}. Nota: {critique.audit_score}. Ressalvas: {len(critique.issues_found)}."
        }

        return {
            "auditor_critique": critique,
            "revision_count": new_rev_count,
            "agent_logs": state["agent_logs"] + [log_entry],
            "status": "audited"
        }

    # =========================================================================
    # CONDICIONAL: Roteador de Decisão do Auditor (Garante Não Ocorrência de Loop Infinito)
    # =========================================================================
    def auditor_decision_router(state: AuditState) -> str:
        critique = state["auditor_critique"]
        rev_count = state["revision_count"]
        max_rev = state["max_revisions"]

        if critique.approved:
            logger.info("[Roteador LangGraph] Auditor APROVOU o relatório. Encaminhando para consolidação final.")
            return "consolidate"

        if rev_count >= max_rev:
            logger.warning(
                f"[Roteador LangGraph] Limite máximo de revisões atingido ({rev_count}/{max_rev}). "
                "Forçando finalização para evitar loop infinito."
            )
            return "consolidate"

        logger.info(
            f"[Roteador LangGraph] Auditor solicitou refinamento ({rev_count}/{max_rev}). Retornando ao nó de Compliance."
        )
        return "refine"

    # =========================================================================
    # NÓ 5: Consolidação do Parecer Final
    # =========================================================================
    def consolidation_node(state: AuditState) -> Dict[str, Any]:
        session_id = state["session_id"]
        doc_name = state["document_name"]
        logger.info(f"==> [Nó 5] Consolidando parecer final executivo para sessão: {session_id}")

        notify(session_id, "auditor", 95, "Gerando Parecer Executivo de Auditoria Consolidado...")

        final_rep = auditor_agent.consolidate_final_report(
            session_id=session_id,
            document_name=doc_name,
            compliance_report=state["compliance_report"],
            critique=state["auditor_critique"],
            revisions_count=state["revision_count"],
            agent_logs=state["agent_logs"]
        )

        notify(
            session_id, "auditor", 100,
            f"Processo concluído com sucesso! Veredito: {final_rep.final_verdict}",
            {"final_verdict": final_rep.final_verdict, "risk_score": final_rep.overall_risk_score}
        )

        log_entry = {
            "agent": "auditor",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "final_consolidation_completed",
            "details": f"Veredito final: {final_rep.final_verdict}. Pontuação de auditoria: {final_rep.audit_quality_score}."
        }

        return {
            "final_report": final_rep,
            "agent_logs": state["agent_logs"] + [log_entry],
            "status": "completed"
        }

    # =========================================================================
    # CONSTRUÇÃO DO GRAFO (StateGraph)
    # =========================================================================
    builder = StateGraph(AuditState)

    builder.add_node("extractor", extractor_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("compliance", compliance_node)
    builder.add_node("auditor", auditor_node)
    builder.add_node("consolidation", consolidation_node)

    # Fluxo Linear Inicial
    builder.add_edge(START, "extractor")
    builder.add_edge("extractor", "researcher")
    builder.add_edge("researcher", "compliance")
    builder.add_edge("compliance", "auditor")

    # Borda Condicional com Proteção Contra Loop Infinito
    builder.add_conditional_edges(
        "auditor",
        auditor_decision_router,
        {
            "consolidate": "consolidation",
            "refine": "compliance"  # Volta para o Compliance com instruções
        }
    )

    builder.add_edge("consolidation", END)

    return builder.compile()
