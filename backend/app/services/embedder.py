"""
Embedder Service
Generates dense vector embeddings using Google's new google-genai SDK.
Uses the native x-goog-api-key authentication (compatible with AQ. keys).
Batches requests in groups of 20 to stay within Render's 30s timeout.
"""

import logging
import time
from typing import List

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialise client once — uses x-goog-api-key header (supports AQ. keys)
_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# gemini-embedding-2 is the latest Google embedding model (3072 dims)
EMBEDDING_MODEL = "gemini-embedding-2"
# Small batch size: avoids Render free-tier 30s request timeouts
BATCH_SIZE = 20
# Delay between batches to respect free-tier rate limits
INTER_BATCH_DELAY = 0.5


def embed_texts(
    texts: List[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> List[List[float]]:
    """
    Embed a list of texts in small batches with retry logic.

    Args:
        texts:     List of strings to embed.
        task_type: Gemini task type hint (RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY).

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
                result = _client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                # New SDK returns a list of ContentEmbedding objects
                batch_embeddings = [e.values for e in result.embeddings]
                all_embeddings.extend(batch_embeddings)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if "429" in str(exc) or "Too Many Requests" in str(exc):
                    logger.error("Rate limit hit (429). Fast failing.")
                    raise RuntimeError("Google API Rate Limit (429) hit. Try again later.") from exc
                
                wait = (attempt + 1) * 2
                logger.warning(
                    "Embedding attempt %d failed: %s. Retrying in %ds…",
                    attempt + 1, exc, wait,
                )
                time.sleep(wait)

        if last_exc is not None:
            logger.error("Embedding batch failed after 3 attempts: %s", last_exc)
            raise RuntimeError(f"Embedding failed: {last_exc}") from last_exc

        # Throttle between batches
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
    embeddings = embed_texts([query], task_type="RETRIEVAL_QUERY")
    return embeddings[0]
