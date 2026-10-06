"""
Testes do Serviço de Cache Semântico
"""
import pytest
from src.services.cache_service import SemanticCacheService, cosine_similarity
from src.services.llm_service import compute_deterministic_embedding


def make_cache() -> SemanticCacheService:
    cache = SemanticCacheService()
    cache.redis_client = None
    cache._memory_cache = []
    cache._stats = {"hits": 0, "misses": 0, "total_saved_tokens": 0}
    return cache


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.5]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    assert abs(cosine_similarity(v1, v2)) < 1e-6


def test_cosine_similarity_empty_vectors():
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], []) == 0.0


def test_cache_miss_then_hit():
    cache = make_cache()
    cache.threshold = 0.99  # threshold alto para controle preciso

    query = "rescisão unilateral contrato"
    emb = compute_deterministic_embedding(query)

    # Miss: cache vazio
    result, score = cache.find_similar(query, emb)
    assert result is None
    assert cache._stats["misses"] == 1

    # Armazena
    cache.store(query, emb, {"results": [{"chunk_id": "chk_1", "text": "Rescisão"}]})

    # Hit: mesma query idêntica → similaridade = 1.0 ≥ 0.99
    cache.threshold = 0.99
    result2, score2 = cache.find_similar(query, emb)
    assert result2 is not None
    assert score2 >= 0.99
    assert cache._stats["hits"] == 1


def test_cache_no_hit_different_queries():
    cache = make_cache()
    cache.threshold = 0.99

    emb1 = compute_deterministic_embedding("penalidade multa contrato")
    emb2 = compute_deterministic_embedding("férias coletivas trabalhista")

    cache.store("penalidade multa contrato", emb1, {"results": []})
    result, score = cache.find_similar("férias coletivas trabalhista", emb2)
    # Queries completamente distintas não devem bater com threshold alto
    assert result is None or score < 0.99


def test_cache_stats_accuracy():
    cache = make_cache()
    cache.threshold = 0.99

    emb = compute_deterministic_embedding("cláusula de responsabilidade civil")
    cache.find_similar("teste miss", emb)  # miss
    cache.store("cláusula de responsabilidade civil", emb, {"results": []}, tokens_saved=300)
    cache.find_similar("cláusula de responsabilidade civil", emb)  # hit

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate_pct"] == 50.0
    assert stats["total_saved_tokens"] == 300


def test_cache_clear():
    cache = make_cache()
    emb = compute_deterministic_embedding("texto qualquer para cache")
    cache.store("texto qualquer", emb, {"results": []})
    assert len(cache._memory_cache) == 1
    cache.clear()
    assert len(cache._memory_cache) == 0
    assert cache._stats["hits"] == 0


def test_deterministic_embedding_is_normalized():
    emb = compute_deterministic_embedding("contrato corporativo brasil")
    norm_sq = sum(v * v for v in emb)
    assert abs(norm_sq - 1.0) < 1e-6


def test_deterministic_embedding_same_text_same_vector():
    text = "LGPD dados pessoais vazamento"
    emb1 = compute_deterministic_embedding(text)
    emb2 = compute_deterministic_embedding(text)
    assert emb1 == emb2
