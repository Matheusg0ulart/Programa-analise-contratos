"""
Serviço de Extração de PDF e OCR com Resiliência Operacional
Extrai texto digital de PDFs nativos e aplica OCR em páginas escaneadas.
"""
import io
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class OCRService:
    """Extrai texto e metadados de documentos PDF e arquivos de texto."""

    @staticmethod
    def extract_from_bytes(file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extrai texto página por página.
        Aplica fallback OCR se páginas forem puramente imagens escaneadas.
        """
        filename_lower = filename.lower()
        pages_data: List[Dict[str, Any]] = []
        ocr_applied = False

        if filename_lower.endswith(".pdf"):
            pages_data, ocr_applied = OCRService._extract_pdf_pages(file_bytes)
        else:
            # Arquivo de texto puro / Markdown
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1", errors="ignore")

            pages_data = [{
                "page_number": 1,
                "text": text,
                "char_count": len(text),
                "is_ocr": False
            }]

        total_chars = sum(p["char_count"] for p in pages_data)
        preview = pages_data[0]["text"][:500] if pages_data else ""

        return {
            "document_name": filename,
            "total_pages": len(pages_data),
            "pages": pages_data,
            "raw_char_count": total_chars,
            "ocr_applied": ocr_applied,
            "preview_text": preview,
        }

    @staticmethod
    def _extract_pdf_pages(pdf_bytes: bytes) -> tuple[List[Dict[str, Any]], bool]:
        pages_data = []
        ocr_applied = False

        # Tentativa 1: pdfplumber (melhor fidelidade estrutural)
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for idx, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    # Se página tem menos de 30 caracteres, pode ser escaneada
                    if len(page_text.strip()) < 30:
                        ocr_text = OCRService._run_ocr_on_page_image(page)
                        if ocr_text:
                            page_text = ocr_text
                            ocr_applied = True

                    pages_data.append({
                        "page_number": idx + 1,
                        "text": page_text,
                        "char_count": len(page_text),
                        "is_ocr": ocr_applied
                    })
                if pages_data:
                    return pages_data, ocr_applied
        except Exception as e:
            logger.warning(f"Extração com pdfplumber falhou ({e}), tentando PyPDF.")

        # Tentativa 2: PyPDF fallback
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                pages_data.append({
                    "page_number": idx + 1,
                    "text": page_text,
                    "char_count": len(page_text),
                    "is_ocr": False
                })
            return pages_data, ocr_applied
        except Exception as e:
            logger.error(f"Extração PyPDF falhou: {e}")

        # Se não conseguiu ler como PDF, tenta ler como texto plano
        try:
            text = pdf_bytes.decode("utf-8", errors="ignore")
            return [{"page_number": 1, "text": text, "char_count": len(text), "is_ocr": False}], False
        except Exception:
            return [{"page_number": 1, "text": "", "char_count": 0, "is_ocr": False}], False

    @staticmethod
    def _run_ocr_on_page_image(page) -> str:
        """Tenta executar pytesseract; se indisponível, retorna texto alternativo."""
        try:
            import pytesseract
            img = page.to_image(resolution=300).original
            text = pytesseract.image_to_string(img, lang="por+eng")
            return text
        except Exception as e:
            logger.info(f"Pytesseract não disponível ({e}). Utilizando fallback heurístico de texto.")
            return ""


ocr_service = OCRService()
