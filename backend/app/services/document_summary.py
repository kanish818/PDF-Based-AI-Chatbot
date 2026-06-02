"""
Lightweight document summary extraction used at ingestion time.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List


STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "have", "will", "your",
    "into", "about", "their", "there", "these", "those", "been", "being", "were",
    "when", "where", "what", "which", "while", "shall", "would", "could", "should",
    "document", "page", "pages", "using", "used", "within", "only", "each", "also",
}


def _detect_document_type(filename: str, combined_text: str) -> str:
    lowered = f"{filename} {combined_text[:4000]}".lower()
    if "resume" in lowered or "curriculum vitae" in lowered or "experience" in lowered:
        return "resume"
    if "training plan" in lowered or "workout" in lowered or "diet" in lowered:
        return "plan"
    if "tutorial" in lowered or "class component" in lowered or "react" in lowered:
        return "tutorial"
    return "document"


def _extract_people_names(text: str) -> List[str]:
    matches = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text)
    seen = []
    for name in matches:
        if name.lower() in STOPWORDS:
            continue
        if name not in seen:
            seen.append(name)
        if len(seen) >= 10:
            break
    return seen


def _extract_topics(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+\-#.]{2,}", text.lower())
    counts = Counter(token for token in tokens if token not in STOPWORDS)
    return [token for token, _ in counts.most_common(8)]


def summarize_document(pages: List[Dict[str, Any]], filename: str) -> Dict[str, str]:
    page_texts = [page.get("text", "").strip() for page in pages if page.get("text", "").strip()]
    combined = "\n\n".join(page_texts)
    intro = " ".join(page_texts[:2])[:1200].strip()
    summary_text = intro or combined[:1200]

    return {
        "summary_text": summary_text,
        "document_type": _detect_document_type(filename, combined),
        "main_topics_json": json.dumps(_extract_topics(combined)),
        "people_names_json": json.dumps(_extract_people_names(combined)),
    }
