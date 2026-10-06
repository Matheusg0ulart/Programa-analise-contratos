"""
Agente 2: Pesquisador / RAG Avançado com Re-ranking e Cache Semântico
Responsabilidade: Indexa chunks no ChromaDB, realiza busca vetorial, re-ranqueia trechos críticos e consulta o cache semântico.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from src.schemas.models import DocumentChunk, RAGSearchResult
from src.services.vector_service import VectorStoreService, vector_service
from src.services.cache_service import semantic_cache, SemanticCacheService
from src.services.llm_service import get_llm_service
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Palavras-chave de alto risco para ponderação de reranking
HIGH_RISK_KEYWORDS = [
    "multa", "penalidade", "retenção", "rescisão", "rescisao", "unilateral",
    "indenização", "indenizacao", "responsabilidade", "lucros cessantes",
    "lgpd", "privacidade", "confidencial", "reajuste", "glosa", "inadimplemento",
    "sanção", "sancao", "tutela", "foro", "execução"
]

DEFAULT_AUDIT_QUERIES = [
    "Multas contratuais, penalidades compensatórias e retenção de créditos",
    "Rescisão antecipada, rescisão unilateral e prazos de aviso prévio",
    "Limitação de responsabilidade civil, cap de indenização e lucros cessantes",
    "Tratamento de dados pessoais, conformidade LGPD e vazamento de informações",
    "Equilíbrio econômico, índices de reajuste e renegociação de preços",
]


class ResearcherAgent:
    """
    Agente de Pesquisa Vetorial e RAG com Cache Semântico e Re-ranking Híbrido.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreService] = None,
        cache: Optional[SemanticCacheService] = None,
        top_k: Optional[int] = None,
        rerank_n: Optional[int] = None
    ):
        self.vector_store = vector_store or vector_service
        self.cache = cache or semantic_cache
        self.llm_service = get_llm_service()
        self.top_k = top_k or settings.RAG_TOP_K
        self.rerank_n = rerank_n or settings.RERANK_TOP_N

    def index_document_chunks(self, chunks: List[DocumentChunk]):
        """Indexa os chunks do documento no ChromaDB."""
        logger.info(f"[Agente 2 - Pesquisador] Indexando {len(chunks)} chunks no ChromaDB.")
        self.vector_store.add_chunks(chunks)

    def search_and_rerank(self, query: str) -> List[RAGSearchResult]:
        """
        Executa pipeline completo:
        1. Consulta Cache Semântico (evita reprocessamento se houver query equivalente).
        2. Busca Vetorial por Similaridade no ChromaDB.
        3. Re-ranking semântico + densidade de termos de risco.
        4. Grava no Cache Semântico.
        """
        logger.info(f"[Agente 2 - Pesquisador] Executando busca para query: '{query}'")

        query_emb = self.llm_service.get_embedding(query)

        # 1. Checagem no Cache Semântico
        cached_result, sim_score = self.cache.find_similar(query, query_emb)
        if cached_result:
            logger.info(f"[Agente 2 - Pesquisador] Retornando resultado do Cache Semântico (Similaridade: {sim_score:.4f})")
            results = [RAGSearchResult(**item) for item in cached_result.get("results", [])]
            for r in results:
                r.is_cached = True
            return results

        # 2. Busca Vetorial no ChromaDB
        raw_matches = self.vector_store.similarity_search(query=query, top_k=self.top_k)

        # 3. Re-ranking Híbrido dos Trechos
        reranked = self._apply_reranking(query, raw_matches)

        top_reranked = reranked[:self.rerank_n]

        # 4. Armazena no Cache Semântico
        serializable_results = [r.model_dump() for r in top_reranked]
        self.cache.store(
            query_text=query,
            query_embedding=query_emb,
            response_data={"results": serializable_results},
            tokens_saved=sum(len(r.text.split()) for r in top_reranked)
        )

        return top_reranked

    def run_multi_query_audit(self, custom_queries: Optional[List[str]] = None) -> List[RAGSearchResult]:
        """Executa a bateria de consultas de auditoria contratual e consolida os melhores trechos desduplicados."""
        queries = custom_queries or DEFAULT_AUDIT_QUERIES
        all_results: Dict[str, RAGSearchResult] = {}

        for q in queries:
            results = self.search_and_rerank(q)
            for res in results:
                if res.chunk_id not in all_results or res.rerank_score > all_results[res.chunk_id].rerank_score:
                    all_results[res.chunk_id] = res

        # Ordena pelo maior rerank_score
        sorted_results = sorted(all_results.values(), key=lambda x: x.rerank_score, reverse=True)
        logger.info(f"[Agente 2 - Pesquisador] Consolidou {len(sorted_results)} trechos únicos de alto impacto.")
        return sorted_results

    def _apply_reranking(self, query: str, matches: List[Dict[str, Any]]) -> List[RAGSearchResult]:
        """
        Algoritmo de Rerank Híbrido:
        Score Final = (0.50 * Similaridade Vetorial) + (0.35 * Densidade Palavras-Chave Risco) + (0.15 * Match Seção)
        """
        reranked = []
        query_words = set(query.lower().split())

        for match in matches:
            text = match.get("text", "")
            meta = match.get("metadata", {})
            vector_sim = match.get("similarity_score", 0.5)

            # Contagem de palavras-chave de risco no trecho
            text_lower = text.lower()
            risk_matches = sum(1 for kw in HIGH_RISK_KEYWORDS if kw in text_lower)
            risk_density_score = min(1.0, risk_matches / 4.0)

            # Match na seção do documento
            section = (meta.get("section_name") or "").lower()
            section_match_score = 0.8 if any(kw in section for kw in ["penalidade", "rescis", "responsab", "multa", "preço"]) else 0.2

            # Score ponderado final
            final_score = (0.50 * vector_sim) + (0.35 * risk_density_score) + (0.15 * section_match_score)

            reranked.append(RAGSearchResult(
                chunk_id=match.get("chunk_id", ""),
                text=text,
                page_number=meta.get("page_number", 1),
                section_name=meta.get("section_name", "Geral"),
                similarity_score=round(vector_sim, 4),
                rerank_score=round(final_score, 4),
                is_cached=False,
                metadata=meta
            ))

        # Ordena decrescente pelo score do reranker
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)
        return reranked


researcher_agent = ResearcherAgent()
