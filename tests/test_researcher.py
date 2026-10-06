"""
Testes do Agente 2 (Pesquisador/RAG) com ChromaDB em memória e Cache Semântico com FakeRedis
"""
import pytest
from src.agents.researcher import ResearcherAgent
from src.services.vector_service import VectorStoreService
from src.services.cache_service import SemanticCacheService
from src.schemas.models import DocumentChunk


def make_chunks(num: int = 5) -> list[DocumentChunk]:
    texts = [
        "CLÁUSULA DE PENALIDADES: Multa contratual de 30% sobre valor global em caso de rescisão antecipada.",
        "LGPD: Os dados pessoais dos colaboradores deverão ser tratados com sigilo e protegidos contra vazamentos.",
        "RESPONSABILIDADE CIVIL: A contratada responde ilimitadamente por danos diretos e lucros cessantes.",
        "RESCISÃO UNILATERAL: A contratante poderá rescindir em 5 dias corridos sem aviso prévio.",
        "REAJUSTE DE PREÇOS: Os valores permanecerão fixos e irreajustáveis durante a vigência.",
    ]
    chunks = []
    for i in range(num):
        t = texts[i % len(texts)]
        chunks.append(DocumentChunk(
            id=f"chk_test_{i}",
            text=t,
            document_name="contrato_teste.txt",
            page_number=i + 1,
            section_name=f"Cláusula {i + 1}",
            chunk_index=i,
            token_estimate=len(t.split()),
            content_hash=f"hash{i:064d}",
        ))
    return chunks


def make_test_researcher() -> ResearcherAgent:
    vs = VectorStoreService(collection_name="test_col", in_memory=True)
    cache = SemanticCacheService()
    # Força cache em memória pura
    cache.redis_client = None
    cache._memory_cache = []
    return ResearcherAgent(vector_store=vs, cache=cache, top_k=5, rerank_n=3)


def test_researcher_indexes_and_searches():
    agent = make_test_researcher()
    chunks = make_chunks(5)
    agent.index_document_chunks(chunks)

    results = agent.search_and_rerank("multa e penalidades contratuais")
    assert len(results) >= 1
    for r in results:
        assert r.chunk_id != ""
        assert r.rerank_score >= 0.0
        assert r.similarity_score >= 0.0


def test_researcher_semantic_cache_hit():
    agent = make_test_researcher()
    chunks = make_chunks(5)
    agent.index_document_chunks(chunks)

    query = "Rescisão unilateral antecipada"
    # Primeira chamada – deve ir ao ChromaDB
    results1 = agent.search_and_rerank(query)
    assert not any(r.is_cached for r in results1)

    # Segunda chamada com mesma query – deve vir do cache semântico
    results2 = agent.search_and_rerank(query)
    assert any(r.is_cached for r in results2)


def test_researcher_reranking_order():
    """Verifica que os resultados estão ordenados por rerank_score decrescente."""
    agent = make_test_researcher()
    agent.index_document_chunks(make_chunks(5))
    results = agent.search_and_rerank("multa penalidade retenção rescisão contratual")
    for i in range(len(results) - 1):
        assert results[i].rerank_score >= results[i + 1].rerank_score


def test_researcher_multi_query_deduplication():
    agent = make_test_researcher()
    agent.index_document_chunks(make_chunks(5))
    results = agent.run_multi_query_audit()
    # Sem duplicatas: cada chunk_id único
    ids = [r.chunk_id for r in results]
    assert len(ids) == len(set(ids))
