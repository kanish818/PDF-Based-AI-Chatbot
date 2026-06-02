"""
PDF Parser Service
Extracts text from each page of a PDF using PyMuPDF.
Falls back to OCR (Tesseract) when extracted text is too short.
"""

import logging
import re
import unicodedata
from typing import List, Dict, Any

import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io

logger = logging.getLogger(__name__)

OCR_THRESHOLD = 50  # characters below which we try OCR


def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ").replace("\uf0b7", "•").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", text)
    text = re.sub(r"(?:(?<=\s)|^)[^\x00-\x7F]{1,2}(?=\s+[A-Za-z])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_primary_text(page: fitz.Page) -> str:
    try:
        blocks = page.get_text("blocks", sort=True)
    except Exception:
        blocks = []

    parts: List[str] = []
    for block in blocks:
        block_type = block[6] if len(block) > 6 else 0
        block_text = block[4] if len(block) > 4 else ""
        if block_type != 0:
            continue
        cleaned = _clean_text(block_text)
        if cleaned:
            parts.append(cleaned)

    if parts:
        return "\n\n".join(parts)

    return _clean_text(page.get_text("text", sort=True))


def _should_try_ocr(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(text) < OCR_THRESHOLD:
        return True
    if not compact:
        return True
    alpha_ratio = sum(ch.isalpha() for ch in compact) / max(len(compact), 1)
    return alpha_ratio < 0.25


def _ocr_page(page: fitz.Page) -> str:
    matrix = fitz.Matrix(3, 3)
    pixmap = page.get_pixmap(matrix=matrix)
    img_bytes = pixmap.tobytes("png")
    pil_image = Image.open(io.BytesIO(img_bytes))
    return _clean_text(
        pytesseract.image_to_string(
            pil_image,
            lang="eng",
            config="--oem 3 --psm 6",
        )
    )


def _normalise_margin_line(line: str) -> str:
    line = re.sub(r"\d+", "#", line.lower())
    line = re.sub(r"[^a-z0-9#]+", " ", line)
    return line.strip()


def _strip_repeated_margins(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(pages) < 3:
        return pages

    first_line_counts: Dict[str, int] = {}
    last_line_counts: Dict[str, int] = {}
    first_lines: List[str] = []
    last_lines: List[str] = []

    for page in pages:
        lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
        first_line = _normalise_margin_line(lines[0]) if lines else ""
        last_line = _normalise_margin_line(lines[-1]) if lines else ""
        first_lines.append(first_line)
        last_lines.append(last_line)
        if 0 < len(first_line) <= 120:
            first_line_counts[first_line] = first_line_counts.get(first_line, 0) + 1
        if 0 < len(last_line) <= 120:
            last_line_counts[last_line] = last_line_counts.get(last_line, 0) + 1

    header_candidates = {
        line for line, count in first_line_counts.items() if count >= max(2, len(pages) // 2)
    }
    footer_candidates = {
        line for line, count in last_line_counts.items() if count >= max(2, len(pages) // 2)
    }

    cleaned_pages: List[Dict[str, Any]] = []
    for page, first_line, last_line in zip(pages, first_lines, last_lines):
        lines = [line for line in page["text"].splitlines()]
        if lines and first_line in header_candidates:
            lines = lines[1:]
        if lines and last_line in footer_candidates:
            lines = lines[:-1]
        cleaned_pages.append({**page, "text": _clean_text("\n".join(lines))})

    return cleaned_pages


def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse a PDF file and return per-page text.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        A list of dicts: [{"page_num": int, "text": str, "filename": str}]
    """
    pages: List[Dict[str, Any]] = []
    filename = file_path.split("/")[-1].split("\\")[-1]

    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        logger.error("Failed to open PDF %s: %s", file_path, exc)
        raise RuntimeError(f"Cannot open PDF: {exc}") from exc

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_num = page_index + 1

        # Primary: sorted block extraction for better layout fidelity.
        try:
            text = _extract_primary_text(page)
        except Exception as exc:
            logger.warning("Page %d text extraction failed: %s", page_num, exc)
            text = ""

        # Fallback: OCR when text is too sparse or looks image/scanned heavy.
        if _should_try_ocr(text):
            logger.info("Page %d text too short (%d chars), attempting OCR.", page_num, len(text))
            try:
                ocr_text = _ocr_page(page)
                if len(ocr_text) > len(text):
                    text = ocr_text
                    logger.info("OCR produced %d chars on page %d.", len(text), page_num)
            except Exception as exc:
                logger.warning("OCR failed on page %d: %s", page_num, exc)

        pages.append({"page_num": page_num, "text": _clean_text(text), "filename": filename})

    doc.close()
    pages = _strip_repeated_margins(pages)

    non_empty_pages = sum(1 for page in pages if page["text"].strip())
    if non_empty_pages != len(pages):
        logger.warning(
            "PDF '%s' extracted text from %d/%d pages.",
            filename,
            non_empty_pages,
            len(pages),
        )

    logger.info("Parsed %d pages from '%s'.", len(pages), filename)
    return pages
