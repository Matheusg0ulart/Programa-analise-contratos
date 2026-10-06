"""
Serviço de Banco Vetorial de Alta Performance com ChromaDB
Gerencia coleções, indexação de chunks contratuais e busca por similaridade.
"""
import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from src.config.settings import settings
from src.schemas.models import DocumentChunk
from src.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Gerencia a persistência e recuperação de vetores via ChromaDB."""

    def __init__(self, collection_name: Optional[str] = None, in_memory: bool = False):
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.llm_service = get_llm_service()
        self.in_memory = in_memory

        if in_memory:
            self.client = chromadb.EphemeralClient()
            logger.info("ChromaDB EphemeralClient (em memória) inicializado.")
        else:
            persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIRECTORY)
            os.makedirs(persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_dir)
            logger.info(f"ChromaDB PersistentClient inicializado em: {persist_dir}")

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Auditoria de Contratos Corporativos"}
        )

    def add_chunks(self, chunks: List[DocumentChunk]):
        """Adiciona ou atualiza chunks na coleção ChromaDB com embeddings calculados."""
        if not chunks:
            return

        ids = [chunk.id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "document_name": chunk.document_name,
                "page_number": chunk.page_number,
                "section_name": chunk.section_name or "Geral",
                "chunk_index": chunk.chunk_index,
                "content_hash": chunk.content_hash,
            }
            for chunk in chunks
        ]

        embeddings = [self.llm_service.get_embedding(doc) for doc in documents]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        logger.info(f"Indexados {len(chunks)} chunks na coleção '{self.collection_name}'.")

    def similarity_search(self, query: str, top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Realiza busca vetorial por proximidade semântica."""
        query_embedding = self.llm_service.get_embedding(query)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, max(1, self.collection.count() or 1)),
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        retrieved = []
        if results and "ids" in results and results["ids"]:
            ids_list = results["ids"][0]
            docs_list = results["documents"][0] if "documents" in results else []
            metas_list = results["metadatas"][0] if "metadatas" in results else []
            dists_list = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(ids_list)

            for i in range(len(ids_list)):
                dist = dists_list[i] if i < len(dists_list) else 0.0
                # Chroma distance normalmente é l2 ou cosine distance. Converter para score de similaridade (0 a 1)
                similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0))) if dist <= 2.0 else max(0.0, 1.0 / (1.0 + dist))

                retrieved.append({
                    "chunk_id": ids_list[i],
                    "text": docs_list[i] if i < len(docs_list) else "",
                    "metadata": metas_list[i] if i < len(metas_list) else {},
                    "similarity_score": round(similarity, 4),
                    "distance": dist,
                })

        return retrieved

    def count(self) -> int:
        return self.collection.count()

    def clear(self):
        """Limpa a coleção atual."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            logger.info(f"Coleção '{self.collection_name}' reinicializada.")
        except Exception as e:
            logger.warning(f"Erro ao limpar coleção: {e}")


# Instância padrão
vector_service = VectorStoreService()
