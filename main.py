"""
Ponto de Entrada Principal – Sistema Multi-Agente Corporativo
Execute com: python main.py
"""
import uvicorn
from src.config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
