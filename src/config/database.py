from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Engine assíncrono (usando asyncpg se postgres, ou aiosqlite se fallback local)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    from src.schemas.db_models import Base
    async with engine.begin() as conn:
        logger.info("Criando tabelas no banco de dados...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tabelas criadas com sucesso.")

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
