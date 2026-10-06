"""
Testes da API FastAPI (rotas REST e WebSocket)
Utiliza TestClient síncrono da Starlette.
"""
import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "llm_provider" in data
    assert "cache" in data


def test_upload_txt_document():
    content = b"CONTRATO DE TESTE\nCLAUSULA PRIMEIRA - DO OBJETO"
    res = client.post(
        "/api/v1/audit/upload",
        files={"file": ("teste.txt", content, "text/plain")},
        data={"auto_start": "false"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert data["document_name"] == "teste.txt"
    assert data["size_bytes"] == len(content)


def test_audit_status_not_found():
    res = client.get("/api/v1/audit/session-nao-existe/status")
    assert res.status_code == 404


def test_audit_report_not_found():
    res = client.get("/api/v1/audit/session-inexistente/report")
    assert res.status_code == 404


def test_sample_contract_endpoint():
    res = client.post("/api/v1/audit/sample")
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert "document_name" in data


def test_cache_stats_endpoint():
    res = client.get("/api/v1/cache/stats")
    assert res.status_code == 200
    data = res.json()
    assert "hits" in data
    assert "misses" in data
    assert "hit_rate_pct" in data


def test_cache_clear_endpoint():
    res = client.post("/api/v1/cache/clear")
    assert res.status_code == 200
    assert res.json()["message"] != ""


def test_dashboard_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "Sistema Multi-Agente" in res.text
    assert "WebSocket" in res.text


def test_audit_markdown_not_found():
    res = client.get("/api/v1/audit/sessao-fake-abc123/markdown")
    assert res.status_code == 404
