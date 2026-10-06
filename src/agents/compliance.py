"""
Agente 3: Jurídico & Compliance
Responsabilidade: Analisa cláusulas de risco e multas com base na legislação brasileira e melhores práticas de governança.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from src.schemas.models import (
    RAGSearchResult,
    ComplianceFinding,
    ComplianceReport,
    RiskLevel
)
from src.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

COMPLIANCE_SYSTEM_PROMPT = """Você é um Consultor Jurídico Sênior e Especialista em Compliance Contratual Corporativo.
Sua missão é auditar rigorosamente instrumentos contratuais, identificando cláusulas leoninas, abusivas ou em desconformidade
com o ordenamento jurídico brasileiro (Código Civil, Lei 13.709/2018 - LGPD, Lei 14.133/2021, Código de Defesa do Consumidor quando aplicável).

Para cada risco identificado, você deve fornecer:
1. clause_title: Título descritivo da cláusula auditada.
2. risk_level: 'Crítico', 'Alto', 'Médio' ou 'Baixo'.
3. risk_description: Análise fundamentada do impacto e risco operacional/financeiro.
4. legal_basis: Dispositivos de leis ou jurisprudência violados ou em risco.
5. offending_text: Trecho literal extraído do documento.
6. mitigation_recommendation: Redação recomendada ou ação mitigatória sugerida.

Sempre responda em formato JSON estruturado."""


class ComplianceAgent:
    """
    Agente Jurídico/Compliance para auditoria de cláusulas e avaliação de riscos regulatórios.
    """

    def __init__(self):
        self.llm_service = get_llm_service()

    def analyze_compliance(
        self,
        document_name: str,
        rag_results: List[RAGSearchResult],
        revision_instructions: Optional[str] = None
    ) -> ComplianceReport:
        """
        Executa a análise de compliance sobre os trechos relevantes fornecidos pelo Agente 2.
        """
        logger.info(f"[Agente 3 - Jurídico/Compliance] Iniciando auditoria para '{document_name}' ({len(rag_results)} trechos).")

        context_texts = []
        for idx, res in enumerate(rag_results, 1):
            context_texts.append(
                f"[Trecho {idx} - Pág {res.page_number} - Seção: {res.section_name} - ChunkID: {res.chunk_id}]\n{res.text}"
            )

        full_context = "\n\n---\n\n".join(context_texts)

        prompt = f"""DOCUMENTO: {document_name}
TRECHOS SELECIONADOS PELO RAG:
{full_context}
"""
        if revision_instructions:
            prompt += f"\n\nINSTRUÇÕES DE REVISÃO DO AUDITOR:\n{revision_instructions}\n"

        prompt += "\nRealize a auditoria jurídica completa e retorne o JSON estruturado com os apontamentos de compliance."

        raw_response = self.llm_service.generate(
            prompt=prompt,
            system_prompt=COMPLIANCE_SYSTEM_PROMPT,
            json_mode=True
        )

        try:
            parsed = json.loads(raw_response)
        except Exception as e:
            logger.warning(f"[Agente 3] Falha no parse JSON direto ({e}), tentando extração de bloco de código.")
            parsed = self._extract_json_from_text(raw_response)

        findings_data = parsed.get("findings", [])
        findings: List[ComplianceFinding] = []

        for item in findings_data:
            # Associa com o chunk mais próximo se não estiver definido
            matched_chunk_id = None
            matched_page = item.get("page_number", 1)

            for res in rag_results:
                if item.get("offending_text", "") and item["offending_text"][:20].lower() in res.text.lower():
                    matched_chunk_id = res.chunk_id
                    matched_page = res.page_number
                    break

            if not matched_chunk_id and rag_results:
                matched_chunk_id = rag_results[0].chunk_id
                matched_page = rag_results[0].page_number

            findings.append(ComplianceFinding(
                id=item.get("id", f"FIND-{len(findings)+1:03d}"),
                clause_title=item.get("clause_title", "Cláusula Auditada"),
                risk_level=RiskLevel(item.get("risk_level", "Médio")),
                risk_description=item.get("risk_description", "Análise de risco realizada."),
                legal_basis=item.get("legal_basis", "Legislação Civil Aplicável"),
                offending_text=item.get("offending_text", ""),
                mitigation_recommendation=item.get("mitigation_recommendation", "Revisar redação com o departamento jurídico."),
                chunk_id=matched_chunk_id,
                page_number=matched_page
            ))

        critical_count = sum(1 for f in findings if f.risk_level == RiskLevel.CRITICO)
        high_count = sum(1 for f in findings if f.risk_level == RiskLevel.ALTO)
        medium_count = sum(1 for f in findings if f.risk_level == RiskLevel.MEDIO)
        low_count = sum(1 for f in findings if f.risk_level == RiskLevel.BAIXO)

        # Cálculo do overall_risk_score
        calculated_score = min(100, (critical_count * 30) + (high_count * 20) + (medium_count * 10) + (low_count * 5))
        final_score = parsed.get("overall_risk_score", calculated_score)

        report = ComplianceReport(
            document_name=document_name,
            overall_risk_score=final_score,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            findings=findings,
            executive_summary=parsed.get(
                "executive_summary",
                f"Auditoria identificou {len(findings)} pontos de risco. Gravidade global calculada em {final_score}/100."
            )
        )

        logger.info(f"[Agente 3 - Jurídico/Compliance] Auditoria concluída. {len(findings)} achados. Score de Risco: {final_score}/100.")
        return report

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Tenta encontrar o primeiro bloco JSON válido no texto."""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return {"findings": [], "overall_risk_score": 50, "executive_summary": "Análise processada."}


compliance_agent = ComplianceAgent()
