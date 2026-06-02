"""
Text Chunker Service
Splits page texts into overlapping chunks using a recursive character splitter strategy.
"""

import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1600
CHUNK_OVERLAP = 220
MIN_PARAGRAPH_LEN = 40

COMMON_HEADINGS = {
    "summary",
    "experience",
    "work experience",
    "projects",
    "education",
    "skills",
    "technical skills",
    "certifications",
    "achievements",
    "profile",
    "objective",
    "introduction",
    "overview",
    "conclusion",
}


def _clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long_paragraph(paragraph: str) -> List[str]:
    if len(paragraph) <= CHUNK_SIZE:
        return [paragraph]

    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    pieces: List[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
            continue
        if current:
            pieces.append(current)
        current = sentence
    if current:
        pieces.append(current)
    return pieces


def _is_heading(paragraph: str) -> bool:
    text = paragraph.strip().rstrip(":")
    if not text or len(text) > 120:
        return False

    lowered = text.lower()
    if lowered in COMMON_HEADINGS:
        return True
    if re.match(r"^\d+(\.\d+)*\s+[A-Z]", text):
        return True
    if text.endswith(":") and len(text.split()) <= 10:
        return True
    if text.isupper() and len(text.split()) <= 10:
        return True
    if text == text.title() and len(text.split()) <= 8 and not text.endswith("."):
        return True
    return False


def _merge_short_paragraphs(paragraphs: List[str]) -> List[str]:
    merged: List[str] = []
    buffer = ""

    for paragraph in paragraphs:
        if _is_heading(paragraph):
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(paragraph)
            continue

        if not buffer:
            buffer = paragraph
            if len(buffer) >= MIN_PARAGRAPH_LEN:
                merged.append(buffer)
                buffer = ""
            continue

        candidate = f"{buffer}\n{paragraph}".strip()
        if len(buffer) < MIN_PARAGRAPH_LEN or len(paragraph) < MIN_PARAGRAPH_LEN:
            buffer = candidate
            if len(buffer) >= MIN_PARAGRAPH_LEN:
                merged.append(buffer)
                buffer = ""
            continue

        merged.append(buffer)
        buffer = paragraph

    if buffer:
        merged.append(buffer)

    return merged


def _paragraphs_from_page(text: str) -> List[str]:
    raw_parts = re.split(r"\n{2,}", text)
    paragraphs: List[str] = []
    for raw in raw_parts:
        cleaned = _clean_text(raw)
        if not cleaned:
            continue
        paragraphs.extend(_split_long_paragraph(cleaned))
    return _merge_short_paragraphs(paragraphs)


def chunk_text(pages: List[Dict[str, Any]], filename: str) -> List[Dict[str, Any]]:
    """
    Split pages into overlapping text chunks.

    Args:
        pages:    List of page dicts from parse_pdf().
        filename: Original PDF filename used in metadata.

    Returns:
        List of chunk dicts: {filename, page_num, chunk_index, text}
    """
    all_chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    for page in pages:
        page_text = page.get("text", "").strip()
        page_num = page.get("page_num", 0)

        if not page_text:
            continue

        paragraphs = _paragraphs_from_page(page_text)
        current_heading = None
        units: List[Dict[str, str]] = []
        for paragraph in paragraphs:
            if _is_heading(paragraph):
                current_heading = paragraph.rstrip(":")
                continue
            units.append(
                {
                    "text": paragraph,
                    "section_heading": current_heading or "",
                }
            )

        current_units: List[Dict[str, str]] = []
        current_length = 0

        def flush_chunk() -> None:
            nonlocal current_units, current_length, chunk_index
            if not current_units:
                return
            chunk_text_part = "\n\n".join(unit["text"] for unit in current_units).strip()
            if chunk_text_part:
                section_heading = next(
                    (unit["section_heading"] for unit in current_units if unit["section_heading"]),
                    "",
                )
                all_chunks.append(
                    {
                        "filename": filename,
                        "page_num": page_num,
                        "chunk_index": chunk_index,
                        "section_heading": section_heading,
                        "text": chunk_text_part,
                    }
                )
                chunk_index += 1

            overlap_units: List[Dict[str, str]] = []
            overlap_length = 0
            for unit in reversed(current_units):
                unit_length = len(unit["text"]) + 2
                if overlap_length + unit_length > CHUNK_OVERLAP:
                    break
                overlap_units.insert(0, unit)
                overlap_length += unit_length
            current_units = overlap_units
            current_length = overlap_length

        for unit in units:
            unit_text = unit["text"]
            unit_length = len(unit_text)

            # Keep section chunks coherent when possible.
            if (
                current_units
                and unit["section_heading"]
                and current_units[-1]["section_heading"] != unit["section_heading"]
                and current_length >= CHUNK_SIZE * 0.6
            ):
                flush_chunk()

            if current_units and current_length + unit_length + 2 > CHUNK_SIZE:
                flush_chunk()

            current_units.append(unit)
            current_length += unit_length + 2

        flush_chunk()

    logger.info("Created %d chunks from %d pages of '%s'.", len(all_chunks), len(pages), filename)
    return all_chunks
