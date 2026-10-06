"""
Modelos de Dados do Sistema Multi-Agente Corporativo
Baseado em Pydantic v2
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)



class RiskLevel(str, Enum):
    BAIXO = "Baixo"
    MEDIO = "Médio"
    ALTO = "Alto"
    CRITICO = "Crítico"


class DocumentChunk(BaseModel):
    """Representa um trecho semântico de um documento."""
    id: str
    text: str
    document_name: str
    page_number: int = 1
    section_name: Optional[str] = None
    chunk_index: int = 0
    token_estimate: int = 0
    content_hash: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Resultado da extração do Agente 1 (Extrator)."""
    document_name: str
    total_pages: int
    total_chunks: int
    ocr_applied: bool = False
    raw_char_count: int = 0
    chunks: List[DocumentChunk]
    preview_text: str = ""
    extracted_at: datetime = Field(default_factory=_now_utc)


class RAGSearchResult(BaseModel):
    """Trecho recuperado e ranqueado pelo Agente 2 (Pesquisador)."""
    chunk_id: str
    text: str
    page_number: int
    section_name: Optional[str] = None
    similarity_score: float
    rerank_score: float
    is_cached: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComplianceFinding(BaseModel):
    """Achado de conformidade e risco identificado pelo Agente 3."""
    id: str
    clause_title: str
    risk_level: RiskLevel
    risk_description: str
    legal_basis: str
    offending_text: str
    mitigation_recommendation: str
    chunk_id: Optional[str] = None
    page_number: Optional[int] = 1


class ComplianceReport(BaseModel):
    """Relatório consolidado pelo Agente 3."""
    document_name: str
    overall_risk_score: int = Field(ge=0, le=100, description="0 = seguro, 100 = risco extremo")
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    findings: List[ComplianceFinding]
    executive_summary: str
    analyzed_at: datetime = Field(default_factory=_now_utc)


class AuditCritique(BaseModel):
    """Avaliação crítica e validação pelo Agente 4 (Auditor Revisor)."""
    approved: bool
    audit_score: int = Field(ge=0, le=100, description="Nota de qualidade e rigor da auditoria")
    issues_found: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    instructions_for_revision: Optional[str] = None
    hallucination_detected: bool = False
    feedback_notes: str = ""


class ConsolidatedAuditReport(BaseModel):
    """Parecer final consolidado após aprovação ou exaustão de revisões."""
    document_name: str
    session_id: str
    audit_timestamp: datetime = Field(default_factory=_now_utc)
    final_verdict: str
    audit_quality_score: int
    overall_risk_score: int
    total_revisions_executed: int
    executive_summary: str
    compliance_findings: List[ComplianceFinding]
    auditor_comments: str
    recommendations: List[str]
    audit_chain_of_custody: List[Dict[str, Any]] = Field(default_factory=list)


class WebSocketEvent(BaseModel):
    """Evento transmitido via WebSocket em tempo real para a interface."""
    event_type: str
    agent_name: str
    timestamp: datetime = Field(default_factory=_now_utc)
    session_id: str
    progress: int = 0
    message: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
