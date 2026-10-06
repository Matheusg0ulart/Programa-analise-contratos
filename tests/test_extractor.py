"""
Testes Unitários do Agente 1 (Extrator Inteligente) e OCR Service
"""
import pytest
from src.agents.extractor import ExtractorAgent
from src.services.ocr_service import ocr_service
from src.schemas.models import DocumentChunk, ExtractionResult


def test_ocr_service_plain_text():
    text = "CONTRATO DE PRESTAÇÃO DE SERVIÇOS\nCLÁUSULA 1 - OBJETO\nPrestação de serviços contínuos."
    data = ocr_service.extract_from_bytes(text.encode("utf-8"), "contrato.txt")
    assert data["total_pages"] == 1
    assert data["document_name"] == "contrato.txt"
    assert "Prestação de serviços" in data["pages"][0]["text"]
    assert data["raw_char_count"] > 0


def test_ocr_service_pdf():
    with open("data/sample_contract.pdf", "rb") as f:
        pdf_bytes = f.read()
    data = ocr_service.extract_from_bytes(pdf_bytes, "sample_contract.pdf")
    assert data["total_pages"] >= 1
    assert len(data["pages"][0]["text"]) > 0
    assert "CONTRATO" in data["pages"][0]["text"]


def test_extractor_agent_chunking():
    sample_text = """CLÁUSULA PRIMEIRA – DO OBJETO
O presente instrumento regula o fornecimento de licenças de software corporativo em nuvem.

CLÁUSULA SEGUNDA – DAS PENALIDADES E MULTAS
O atraso ensejará aplicação de multa compensatória de 30% do valor do contrato.
Fica autorizada a retenção integral de pagamentos futuros.

CLÁUSULA TERCEIRA – DA RESCISÃO
A Contratante poderá rescindir o ajuste com aviso prévio de 5 dias corridos."""

    agent = ExtractorAgent(chunk_size=150, chunk_overlap=30)
    result = agent.process_document(sample_text.encode("utf-8"), "teste_minuta.txt")

    assert isinstance(result, ExtractionResult)
    assert result.total_chunks >= 2
    assert len(result.chunks) == result.total_chunks

    # Verifica estrutura dos chunks
    for chunk in result.chunks:
        assert isinstance(chunk, DocumentChunk)
        assert chunk.id.startswith("chk_")
        assert len(chunk.content_hash) == 64  # SHA-256
        assert chunk.token_estimate > 0


def test_extractor_agent_empty_document():
    agent = ExtractorAgent()
    result = agent.process_document(b"", "documento_vazio.txt")
    assert result.total_chunks == 1
    assert "vazio" in result.chunks[0].text.lower()
