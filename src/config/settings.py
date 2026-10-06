"""
Configurações Globais do Sistema Multi-Agente Corporativo
Baseado em Pydantic Settings
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    # Provedor de LLM
    LLM_PROVIDER: str = Field(default="mock", description="mock | openai | gemini | ollama")
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_MODEL: str = Field(default="gemini-1.5-pro")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3")

    # Cache Semântico e Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_ENABLED: bool = Field(default=True)
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = Field(default=0.88)
    SEMANTIC_CACHE_TTL_SECONDS: int = Field(default=86400)

    # ChromaDB
    CHROMA_PERSIST_DIRECTORY: str = Field(default="./data/chroma_db")
    CHROMA_COLLECTION_NAME: str = Field(default="corporate_audit_chunks")

    # Chunking e RAG
    CHUNK_SIZE: int = Field(default=1000)
    CHUNK_OVERLAP: int = Field(default=200)
    RAG_TOP_K: int = Field(default=6)
    RERANK_TOP_N: int = Field(default=4)

    # Orquestração e Auditoria
    MAX_AUDIT_REVISIONS: int = Field(default=2, description="Limite máximo de refinamento do auditor para evitar loops")

    # Servidor FastAPI
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=True)

    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./multiagent.db")
    
    # Auth
    SECRET_KEY: str = Field(default="sua_chave_secreta_super_segura_mudar_em_prod")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 7) # 1 week

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )



settings = Settings()
