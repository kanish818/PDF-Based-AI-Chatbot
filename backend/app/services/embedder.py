"""
Embedder Service
Generates dense vector embeddings using Google's text-embedding-004 model via the
google-generativeai SDK. Batches requests in groups of 100 to respect API limits.
"""

import logging
from typing import List

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure the SDK once at import time
genai.configure(api_key=settings.GEMINI_API_KEY)

# `text-embedding-004` no longer works with the current Gemini `embedContent`
# path used by this service. `gemini-embedding-001` is the supported text
# embedding model in Google's current public docs for this API shape.
EMBEDDING_MODEL = "models/gemini-embedding-001"
BATCH_SIZE = 100


def embed_texts(
    texts: List[str],
    task_type: str = "retrieval_document",
) -> List[List[float]]:
    """
    Embed a list of texts in batches.

    Args:
        texts:     List of strings to embed.
        task_type: Gemini task type hint (e.g. "retrieval_document", "retrieval_query").

    Returns:
        List of embedding vectors (each a list of floats).
    """
    if not texts:
        return []

    all_embeddings: List[List[float]] = []

    for batch_start in range(0, len(texts), BATCH_SIZE):
        batch = texts[batch_start : batch_start + BATCH_SIZE]
        logger.info(
            "Embedding batch %d–%d of %d texts.",
            batch_start + 1,
            batch_start + len(batch),
            len(texts),
        )
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=batch,
                task_type=task_type,
            )
            batch_embeddings: List[List[float]] = result["embedding"]
            all_embeddings.extend(batch_embeddings)
        except Exception as exc:
            logger.error("Embedding batch failed: %s", exc)
            raise RuntimeError(f"Embedding failed: {exc}") from exc

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
