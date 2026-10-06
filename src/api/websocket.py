"""
Gerenciador de Conexões WebSocket e Streaming em Tempo Real
Permite envio de eventos granulares durante a orquestração dos agentes autônomos.
"""
import asyncio
import json
import logging
from typing import Dict, List
from fastapi import WebSocket
from src.schemas.models import WebSocketEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerencia conexões WebSocket ativas por session_id."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        logger.info(f"WebSocket conectado para sessão: {session_id} (Total: {len(self.active_connections[session_id])})")

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        logger.info(f"WebSocket desconectado para sessão: {session_id}")

    async def broadcast_event(self, session_id: str, event: WebSocketEvent):
        """Envia um evento estruturado para todos os clientes conectados à sessão."""
        if session_id in self.active_connections:
            payload = event.model_dump_json()
            disconnected = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(payload)
                except Exception as e:
                    logger.warning(f"Erro ao enviar mensagem WebSocket: {e}")
                    disconnected.append(connection)

            for dead_conn in disconnected:
                self.disconnect(dead_conn, session_id)


manager = ConnectionManager()


def dispatch_event_sync(session_id: str, agent_name: str, progress: int, message: str, payload: dict = None):
    """
    Função utilitária thread-safe / event-loop aware para emitir eventos WebSocket
    a partir de nós síncronos do LangGraph.
    """
    event = WebSocketEvent(
        event_type="agent_update" if progress < 100 else "completed",
        agent_name=agent_name,
        session_id=session_id,
        progress=progress,
        message=message,
        payload=payload or {}
    )

    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(manager.broadcast_event(session_id, event), loop)
    except RuntimeError:
        # Nenhum loop em execução no thread atual
        try:
            asyncio.run(manager.broadcast_event(session_id, event))
        except Exception as e:
            logger.debug(f"Não foi possível transmitir evento via loop síncrono: {e}")
