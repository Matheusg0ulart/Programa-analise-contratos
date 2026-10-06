"""
Definição de Estado Tipado para o LangGraph
Controla a transição e integridade das informações entre os agentes autônomos.
"""
from typing import TypedDict, List, Dict, Any, Optional
from src.schemas.models import (
    DocumentChunk,
    RAGSearchResult,
    ComplianceReport,
    AuditCritique,
    ConsolidatedAuditReport
)


class AuditState(TypedDict):
    """Estado global compartilhado entre os agentes de IA."""
    session_id: str
    document_name: str
    raw_bytes: bytes
    raw_text: str
    chunks: List[DocumentChunk]
    rag_results: List[RAGSearchResult]
    compliance_report: Optional[ComplianceReport]
    auditor_critique: Optional[AuditCritique]
    revision_count: int
    max_revisions: int
    status: str
    agent_logs: List[Dict[str, Any]]
    final_report: Optional[ConsolidatedAuditReport]
