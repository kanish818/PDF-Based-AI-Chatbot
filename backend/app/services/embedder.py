"""
Embedder Service
Generates dense vector embeddings using Google's Gemini embedding model.
Supports both permanent API keys (AIzaSy...) and OAuth tokens (AQ...).
Batches requests in groups of 20 to stay well within Render's 30s timeout.
"""

import logging
import time
from typing import List

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure the SDK once at import time
genai.configure(api_key=settings.GEMINI_API_KEY)

# gemini-embedding-001 is the current supported embedding model
EMBEDDING_MODEL = "models/gemini-embedding-001"
# Smaller batch size: avoids Render free-tier 30s request timeouts
BATCH_SIZE = 20
# Delay between batches (seconds) to respect rate limits on free API tier
INTER_BATCH_DELAY = 0.5


def embed_texts(
    texts: List[str],
    task_type: str = "retrieval_document",
) -> List[List[float]]:
    """
    Embed a list of texts in small batches with retry logic.

    Args:
        texts:     List of strings to embed.
        task_type: Gemini task type hint.

    Returns:
        List of embedding vectors (each a list of floats).
    """
    if not texts:
        return []

    all_embeddings: List[List[float]] = []
    total = len(texts)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = texts[batch_start: batch_start + BATCH_SIZE]
        logger.info(
            "Embedding batch %d–%d of %d texts.",
            batch_start + 1,
            batch_start + len(batch),
            total,
        )

        last_exc = None
        for attempt in range(3):  # up to 3 retries
            try:
                result = genai.embed_content(
                    model=EMBEDDING_MODEL,
                    content=batch,
                    task_type=task_type,
                )
                # The SDK returns {"embedding": [...]} for a list of inputs
                raw = result.get("embedding", [])
                # Normalise: single-text returns a flat list, multi-text returns list-of-lists
                if raw and not isinstance(raw[0], list):
                    raw = [raw]
                all_embeddings.extend(raw)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                wait = (attempt + 1) * 2
                logger.warning(
                    "Embedding attempt %d failed: %s. Retrying in %ds…",
                    attempt + 1, exc, wait,
                )
                time.sleep(wait)

        if last_exc is not None:
            logger.error("Embedding batch failed after 3 attempts: %s", last_exc)
            raise RuntimeError(f"Embedding failed: {last_exc}") from last_exc

        # Throttle between batches to avoid API rate-limit errors
        if batch_start + BATCH_SIZE < total:
            time.sleep(INTER_BATCH_DELAY)

    return all_embeddings


def embed_query(query: str) -> List[float]:
    """
    Embed a single query string with the retrieval_query task type.

    Args:
        query: The user's search query.

    Returns:
        A single embedding vector (list of floats).
    """
    embeddings = embed_texts([query], task_type="retrieval_query")
    return embeddings[0]
