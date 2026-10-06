"""
Agente 1: Extrator Inteligente de Documentos
Responsabilidade: Processa PDFs/textos, executa OCR quando necessário e realiza chunking semântico estruturado.
"""
import hashlib
import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from src.schemas.models import DocumentChunk, ExtractionResult
from src.services.ocr_service import ocr_service
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Padrões de seções contratuais típicas no Brasil
SECTION_PATTERNS = [
    re.compile(r"^(CLÁUSULA\s+[A-Z0-9ªº\.\-]+(?:\s*–\s*|\s*-\s*|\s*:\s*)?[^\n]*)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(SEÇÃO\s+[A-Z0-9\.\-]+(?:\s*–\s*|\s*-\s*|\s*:\s*)?[^\n]*)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(CAPÍTULO\s+[A-Z0-9\.\-]+(?:\s*–\s*|\s*-\s*|\s*:\s*)?[^\n]*)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(DO\s+OBJETO|DAS\s+OBRIGAÇÕES|DO\s+PREÇO|DAS\s+PENALIDADES|DA\s+RESCISÃO|DA\s+VIGÊNCIA|DA\s+CONFIDENCIALIDADE|DO\s+FORO)[^\n]*", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(Art\.?\s*\d+[º\.]?[^\n]*)", re.IGNORECASE | re.MULTILINE),
]


class ExtractorAgent:
    """
    Agente autônomo responsável pela extração, normalização e chunking semântico.
    """

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def process_document(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Executa extração completa com OCR e chunking semântico."""
        logger.info(f"[Agente 1 - Extrator] Iniciando extração do documento: {filename}")

        # Extração das páginas e OCR se necessário
        extraction_data = ocr_service.extract_from_bytes(file_bytes, filename)
        pages = extraction_data["pages"]

        all_chunks: List[DocumentChunk] = []
        chunk_idx = 0

        for page in pages:
            page_num = page["page_number"]
            page_text = page["text"]

            if not page_text or not page_text.strip():
                continue

            page_chunks = self._chunk_page_text(page_text, page_num, filename, chunk_idx)
            chunk_idx += len(page_chunks)
            all_chunks.extend(page_chunks)

        # Se nenhum chunk foi gerado (texto vazio), gera chunk vazio seguro
        if not all_chunks:
            all_chunks.append(DocumentChunk(
                id=f"chunk-{uuid.uuid4().hex[:8]}",
                text="[Documento vazio ou ilegível]",
                document_name=filename,
                page_number=1,
                chunk_index=0,
                token_estimate=5,
                content_hash=hashlib.sha256(b"").hexdigest(),
                metadata={"empty": True}
            ))

        logger.info(f"[Agente 1 - Extrator] Concluído. {len(all_chunks)} chunks semânticos gerados.")

        return ExtractionResult(
            document_name=filename,
            total_pages=len(pages),
            total_chunks=len(all_chunks),
            ocr_applied=extraction_data["ocr_applied"],
            raw_char_count=extraction_data["raw_char_count"],
            chunks=all_chunks,
            preview_text=extraction_data["preview_text"]
        )

    def _chunk_page_text(self, text: str, page_num: int, filename: str, start_index: int) -> List[DocumentChunk]:
        """Divide o texto da página respeitando limites semânticos de cláusulas e parágrafos."""
        chunks: List[DocumentChunk] = []
        paragraphs = text.split("\n\n")

        current_section = f"Página {page_num}"
        current_buffer = []
        current_len = 0
        local_idx = start_index

        for para in paragraphs:
            para_clean = para.strip()
            if not para_clean:
                continue

            # Detecta se o parágrafo inicia uma nova seção/cláusula
            detected_sec = self._detect_section_header(para_clean)
            if detected_sec:
                current_section = detected_sec

            para_len = len(para_clean)

            # Se o buffer já ultrapassou o tamanho alvo, consolida o chunk atual
            if current_len + para_len > self.chunk_size and current_buffer:
                chunk_text = "\n\n".join(current_buffer)
                chunks.append(self._build_chunk(chunk_text, filename, page_num, current_section, local_idx))
                local_idx += 1

                # Mantém sobreposição (overlap) semântica dos últimos parágrafos
                overlap_chars = 0
                overlap_buffer = []
                for p in reversed(current_buffer):
                    if overlap_chars + len(p) <= self.chunk_overlap:
                        overlap_buffer.insert(0, p)
                        overlap_chars += len(p)
                    else:
                        break

                current_buffer = overlap_buffer
                current_len = sum(len(p) for p in current_buffer)

            current_buffer.append(para_clean)
            current_len += para_len

        # Limpa o buffer restante
        if current_buffer:
            chunk_text = "\n\n".join(current_buffer)
            chunks.append(self._build_chunk(chunk_text, filename, page_num, current_section, local_idx))

        return chunks

    def _detect_section_header(self, text: str) -> Optional[str]:
        first_line = text.split("\n")[0].strip()
        for pattern in SECTION_PATTERNS:
            match = pattern.search(first_line)
            if match:
                return match.group(0).strip()[:80]
        return None

    def _build_chunk(self, text: str, filename: str, page_num: int, section: str, idx: int) -> DocumentChunk:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        tokens_est = max(1, int(len(text.split()) * 1.3))
        chunk_id = f"chk_{page_num}_{idx}_{content_hash[:8]}"

        return DocumentChunk(
            id=chunk_id,
            text=text,
            document_name=filename,
            page_number=page_num,
            section_name=section,
            chunk_index=idx,
            token_estimate=tokens_est,
            content_hash=content_hash,
            metadata={
                "page": page_num,
                "section": section,
                "chars": len(text)
            }
        )


extractor_agent = ExtractorAgent()
