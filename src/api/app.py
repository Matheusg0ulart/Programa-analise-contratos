"""
Aplicação Principal FastAPI
Configura rotas REST, WebSockets, arquivos estáticos e templates HTML.
"""
import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from src.config.settings import settings
from src.api.routes import router as api_router
from src.api.auth_routes import router as auth_router
from src.api.websocket import manager

# Configuração de logging estruturado
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("sistema-multi-agente")

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from src.config.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Inicialização (roda antes da aplicação receber requisições)
    await init_db()
    yield
    # Cleanup
    pass

app = FastAPI(
    title="Sistema Multi-Agente Corporativo com RAG Avançado",
    description="Auditoria autônoma colaborativa de contratos, editais e relatórios corporativos com IA e Engenharia de Dados.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão de Rotas REST
app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_router)

# Diretórios estáticos e templates (relativos a src/)
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(SRC_DIR, "static")
TEMPLATES_DIR = os.path.join(SRC_DIR, "templates")


os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.websocket("/ws/audit/{session_id}")
async def websocket_audit_endpoint(websocket: WebSocket, session_id: str):
    """Canal WebSocket para streaming em tempo real do ciclo de vida dos agentes."""
    await manager.connect(websocket, session_id)
    try:
        while True:
            # Mantém conexão viva ouvindo possíveis comandos do cliente (ex: ping/cancel)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.warning(f"Exceção no WebSocket da sessão {session_id}: {e}")
        manager.disconnect(websocket, session_id)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Página inicial com Dashboard Interativo de Auditoria Corporativa."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_version": "2.0.0"}
    )
