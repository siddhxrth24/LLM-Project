import os
import re
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.core.logging_config import logger


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing path separators and unsafe characters."""
    base = os.path.basename(filename)
    # Replace spaces and special characters with underscores, keeping alphanumeric, dots, and hyphens
    sanitized = re.sub(r"[^\w\s\.-]", "", base).strip()
    sanitized = re.sub(r"[\s]+", "_", sanitized)
    if not sanitized:
        sanitized = "unnamed_document"
    return sanitized


def extract_with_ocr(file_path: Path | str, page_num: int) -> str:
    """Extract text from a specific PDF page using OCR (Tesseract) if enabled."""
    if not settings.OCR_ENABLED:
        return ""

    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image
        import io

        if settings.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH

        doc = fitz.open(str(file_path))
        page_index = max(0, page_num - 1)
        if page_index >= len(doc):
            return ""

        page = doc[page_index]
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))
        ocr_text = pytesseract.image_to_string(image)
        doc.close()
        return ocr_text.strip()
    except Exception as e:
        logger.warning(f"OCR extraction failed for {file_path} page {page_num}: {e}")
        return ""


def extract_pdf(file_path: Path | str) -> list[tuple[int, str]]:
    """
    Extract text from a PDF file page-by-page.
    Returns a list of tuples: (page_number_1_indexed, text).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    extracted_pages: list[tuple[int, str]] = []

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        for page_index in range(len(doc)):
            page_num = page_index + 1
            page = doc[page_index]
            text = page.get_text("text").strip()

            # If text is minimal and OCR is enabled, attempt OCR fallback
            if len(text) < 20 and settings.OCR_ENABLED:
                ocr_text = extract_with_ocr(path, page_num)
                if len(ocr_text) > len(text):
                    text = ocr_text

            extracted_pages.append((page_num, text))

        doc.close()
    except Exception as exc:
        logger.error(f"Error extracting text from PDF {path}: {exc}")
        raise RuntimeError(f"Failed to extract text from PDF: {exc}") from exc

    return extracted_pages


def extract_pptx(file_path: Path | str) -> list[tuple[int, str]]:
    """
    Extract text from a PPTX file slide-by-slide.
    Returns a list of tuples: (slide_number_1_indexed, text).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PPTX file not found: {path}")

    extracted_slides: list[tuple[int, str]] = []

    try:
        from pptx import Presentation

        prs = Presentation(str(path))
        for slide_index, slide in enumerate(prs.slides):
            slide_num = slide_index + 1
            slide_text_pieces: list[str] = []

            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        p_text = paragraph.text.strip()
                        if p_text:
                            slide_text_pieces.append(p_text)
                elif shape.has_table:
                    for row in shape.table.rows:
                        row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_text:
                            slide_text_pieces.append(" | ".join(row_text))

            slide_text = "\n".join(slide_text_pieces).strip()
            extracted_slides.append((slide_num, slide_text))
    except Exception as exc:
        logger.error(f"Error extracting text from PPTX {path}: {exc}")
        raise RuntimeError(f"Failed to extract text from PPTX: {exc}") from exc

    return extracted_slides


def chunk_text(
    pages: list[tuple[int, str]],
    chunk_size: int = 400,
    overlap: int = 80,
    source_type: str = "pdf",
    source_filename: str = "",
) -> list[dict[str, Any]]:
    """
    Split extracted page/slide texts into overlapping chunks with source metadata.

    Args:
        pages: List of (page_or_slide_number, text)
        chunk_size: Target number of words per chunk (~400 words)
        overlap: Number of overlapping words between consecutive chunks
        source_type: 'pdf' or 'pptx'
        source_filename: Original file name for citations

    Returns:
        List of dicts containing chunk index, content, page/slide info, and metadata.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    chunks: list[dict[str, Any]] = []
    chunk_index = 0
    step = chunk_size - overlap

    for unit_num, text in pages:
        cleaned_text = re.sub(r"\s+", " ", text).strip()
        if not cleaned_text:
            continue

        words = cleaned_text.split(" ")
        if len(words) <= chunk_size:
            # Single chunk for this page/slide
            chunk_dict: dict[str, Any] = {
                "chunk_index": chunk_index,
                "content": cleaned_text,
                "page_number": unit_num if source_type.lower() == "pdf" else None,
                "slide_number": unit_num if source_type.lower() == "pptx" else None,
                "source_filename": source_filename,
                "metadata": {
                    "source_type": source_type,
                    "source_filename": source_filename,
                    "unit_num": unit_num,
                    "word_count": len(words),
                },
            }
            chunks.append(chunk_dict)
            chunk_index += 1
        else:
            # Windowing for long pages
            for start in range(0, len(words), step):
                chunk_words = words[start : start + chunk_size]
                if not chunk_words:
                    break

                chunk_content = " ".join(chunk_words).strip()
                # Do not emit extremely small leftover fragments
                if len(chunk_words) < 20 and start > 0:
                    break

                chunk_dict = {
                    "chunk_index": chunk_index,
                    "content": chunk_content,
                    "page_number": unit_num if source_type.lower() == "pdf" else None,
                    "slide_number": unit_num if source_type.lower() == "pptx" else None,
                    "source_filename": source_filename,
                    "metadata": {
                        "source_type": source_type,
                        "source_filename": source_filename,
                        "unit_num": unit_num,
                        "word_count": len(chunk_words),
                    },
                }
                chunks.append(chunk_dict)
                chunk_index += 1

                if start + chunk_size >= len(words):
                    break

    return chunks
