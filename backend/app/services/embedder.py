"""
Embedder Service
Generates dense vector embeddings using Google's new google-genai SDK.
Uses the native x-goog-api-key authentication (compatible with AQ. keys).
Batches requests in groups of 100 to minimise round-trips.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import List

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialise client once — uses x-goog-api-key header (supports AQ. keys)
_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# text-embedding-004: fast, 768-dim, ideal for RAG retrieval on free tier
EMBEDDING_MODEL = "text-embedding-004"
# Gemini embedding API supports up to 100 texts per call — use it fully
BATCH_SIZE = 100
# Minimal delay between batches — only needed to avoid 429s
INTER_BATCH_DELAY = 0.1
EMBED_TIMEOUT_SECONDS = 45


def embed_texts(
    texts: List[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    heartbeat=None,
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
            executor = None
            try:
                if heartbeat:
                    heartbeat()
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(
                    _client.models.embed_content,
                    model=EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                result = future.result(timeout=EMBED_TIMEOUT_SECONDS)
                # New SDK returns a list of ContentEmbedding objects
                batch_embeddings = [e.values for e in result.embeddings]
                all_embeddings.extend(batch_embeddings)
                last_exc = None
                break
            except FuturesTimeoutError as exc:
                last_exc = exc
                logger.error("Embedding request timed out after %ds.", EMBED_TIMEOUT_SECONDS)
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
            finally:
                if executor is not None:
                    executor.shutdown(wait=False, cancel_futures=True)

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
