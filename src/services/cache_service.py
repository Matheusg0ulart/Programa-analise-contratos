"""
Serviço de Cache Semântico de Alta Performance com Redis e Fallback Inteligente
Evita chamadas repetidas a APIs de LLM utilizando similaridade de cosseno de embeddings.
"""
import json
import logging
import math
from typing import Dict, Any, Optional, List, Tuple
from src.config.settings import settings

logger = logging.getLogger(__name__)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calcula a similaridade de cosseno entre dois vetores."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCacheService:
    """
    Gerenciador de Cache Semântico com Redis e fallback em fakeredis / in-memory.
    """

    def __init__(self):
        self.threshold = settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD
        self.ttl = settings.SEMANTIC_CACHE_TTL_SECONDS
        self.redis_client = None
        self.is_connected_real_redis = False
        self._memory_cache: List[Dict[str, Any]] = []
        self._stats = {"hits": 0, "misses": 0, "total_saved_tokens": 0}
        self._init_redis()

    def _init_redis(self):
        """Tenta conectar ao Redis real; caso indisponível, ativa fakeredis/memória."""
        if not settings.REDIS_ENABLED:
            logger.info("Redis desativado nas configurações. Usando cache semântico em memória.")
            return

        try:
            import redis
            client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1.5)
            client.ping()
            self.redis_client = client
            self.is_connected_real_redis = True
            logger.info(f"Conectado ao Redis com sucesso em {settings.REDIS_URL}")
        except Exception as e:
            logger.warning(f"Não foi possível conectar ao Redis real ({e}). Ativando fallback fakeredis/em memória.")
            try:
                import fakeredis
                self.redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
                self.is_connected_real_redis = False
                logger.info("FakeRedis ativado com sucesso para cache semântico em memória.")
            except Exception as e2:
                logger.warning(f"Fakeredis indisponível ({e2}). Usando lista em memória.")
                self.redis_client = None

    def find_similar(self, query_text: str, query_embedding: List[float]) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Busca entrada semanticamente equivalente no cache.
        Retorna (dados_cacheados, similaridade_encontrada).
        """
        best_match = None
        best_score = -1.0

        items = self._get_all_cache_entries()

        for item in items:
            cached_emb = item.get("embedding", [])
            sim = cosine_similarity(query_embedding, cached_emb)
            if sim > best_score:
                best_score = sim
                best_match = item

        if best_match and best_score >= self.threshold:
            self._stats["hits"] += 1
            self._stats["total_saved_tokens"] += best_match.get("tokens_saved", 500)
            logger.info(
                f"[Cache Semântico HIT] Query: '{query_text[:40]}...' bateu com '{best_match.get('query', '')[:40]}...' (Score: {best_score:.4f} >= {self.threshold})"
            )
            return best_match.get("response"), best_score

        self._stats["misses"] += 1
        return None, best_score

    def store(self, query_text: str, query_embedding: List[float], response_data: Dict[str, Any], tokens_saved: int = 500):
        """Armazena nova consulta no cache semântico."""
        entry = {
            "query": query_text,
            "embedding": query_embedding,
            "response": response_data,
            "tokens_saved": tokens_saved,
        }

        if self.redis_client:
            try:
                cache_id = f"semcache:{len(self._get_all_cache_entries()) + 1}"
                serialized = json.dumps(entry, ensure_ascii=False)
                self.redis_client.set(cache_id, serialized, ex=self.ttl)
                self.redis_client.sadd("semcache:index", cache_id)
            except Exception as e:
                logger.error(f"Erro ao salvar no Redis: {e}. Salvando em memória local.")
                self._memory_cache.append(entry)
        else:
            self._memory_cache.append(entry)

    def _get_all_cache_entries(self) -> List[Dict[str, Any]]:
        """Recupera todas as entradas do cache."""
        entries = []
        if self.redis_client:
            try:
                keys = self.redis_client.smembers("semcache:index")
                for key in keys:
                    val = self.redis_client.get(key)
                    if val:
                        entries.append(json.loads(val))
            except Exception as e:
                logger.error(f"Erro ao ler entradas do Redis: {e}")
                return self._memory_cache
            return entries
        return self._memory_cache

    def clear(self):
        """Limpa todo o cache semântico."""
        if self.redis_client:
            try:
                keys = self.redis_client.smembers("semcache:index")
                for key in keys:
                    self.redis_client.delete(key)
                self.redis_client.delete("semcache:index")
            except Exception:
                pass
        self._memory_cache.clear()
        self._stats = {"hits": 0, "misses": 0, "total_saved_tokens": 0}

    def get_stats(self) -> Dict[str, Any]:
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0.0
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate_pct": round(hit_rate, 2),
            "total_saved_tokens": self._stats["total_saved_tokens"],
            "backend": "redis" if self.is_connected_real_redis else "fakeredis/in-memory",
            "total_cached_queries": len(self._get_all_cache_entries()),
        }


# Instância global do serviço de cache
semantic_cache = SemanticCacheService()
