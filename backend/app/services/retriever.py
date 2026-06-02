"""
Retriever Service
Implements hybrid search by combining:
  1. Vector search (ChromaDB cosine similarity)
  2. BM25 keyword search (rank-bm25)
Fused with Reciprocal Rank Fusion (RRF).
"""

import logging
import re
from typing import List, Dict, Any

from rank_bm25 import BM25Okapi

from app.services import vector_store

logger = logging.getLogger(__name__)

RRF_K = 60  # RRF constant (standard value)
SUMMARY_HINTS = ("summary", "summarize", "overview", "important points", "main points")
ACTION_HINTS = ("action", "next step", "todo", "task", "recommendation", "plan")


def expand_query_for_retrieval(query: str) -> str:
    lowered = query.lower()
    hints: List[str] = []

    if any(hint in lowered for hint in SUMMARY_HINTS):
        hints.append("summary overview main points key ideas important details")
    if any(hint in lowered for hint in ACTION_HINTS):
        hints.append("action items tasks recommendations instructions steps checklist")
    if "name" in lowered:
        hints.append("name full name person candidate author")
    if "skill" in lowered:
        hints.append("skills technologies tools frameworks expertise")
    if "project" in lowered:
        hints.append("projects work experience accomplishments responsibilities")

    if not hints:
        return query
    return f"{query} {' '.join(hints)}"


def choose_retrieval_count(query: str) -> int:
    lowered = query.lower()
    if any(hint in lowered for hint in SUMMARY_HINTS + ACTION_HINTS):
        return 8
    return 5


def _tokenize(text: str) -> List[str]:
    """Simple whitespace tokeniser for BM25."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    key: str = "chunk_id",
) -> List[Dict[str, Any]]:
    """
    Fuse multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        ranked_lists: Each inner list is a ranked list of result dicts.
        key:          The dict field used as the unique identifier for dedup.

    Returns:
        Combined list sorted by descending RRF score.
    """
    rrf_scores: Dict[str, float] = {}
    item_map: Dict[str, Dict[str, Any]] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list):
            item_key = item[key]
            rrf_scores[item_key] = rrf_scores.get(item_key, 0.0) + 1.0 / (rank + 1 + RRF_K)
            if item_key not in item_map:
                item_map[item_key] = item

    sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)
    fused: List[Dict[str, Any]] = []
    for k in sorted_keys:
        result = dict(item_map[k])
        result["score"] = rrf_scores[k]
        fused.append(result)

    return fused


def _term_overlap_score(query_tokens: List[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = set(_tokenize(text))
    if not text_tokens:
        return 0.0
    matched = sum(1 for token in query_tokens if token in text_tokens)
    return matched / max(len(set(query_tokens)), 1)


def _rerank_results(query: str, results: List[Dict[str, Any]], n_results: int) -> List[Dict[str, Any]]:
    query_tokens = _tokenize(query)
    lowered_query = query.lower()
    reranked: List[Dict[str, Any]] = []

    for item in results:
        overlap = _term_overlap_score(query_tokens, item.get("text", ""))
        section_heading = item.get("section_heading", "")
        section_overlap = _term_overlap_score(query_tokens, section_heading)
        dense_score = float(item.get("vector_score", 0.0))
        bm25_score = float(item.get("bm25_score", 0.0))
        bm25_norm = min(bm25_score / 8.0, 1.0)
        exact_phrase_bonus = 0.2 if lowered_query and lowered_query in item.get("text", "").lower() else 0.0
        rerank_score = (
            float(item.get("score", 0.0))
            + overlap * 1.1
            + section_overlap * 0.35
            + dense_score * 0.25
            + bm25_norm * 0.15
            + exact_phrase_bonus
        )
        reranked_item = dict(item)
        reranked_item["score"] = rerank_score
        reranked.append(reranked_item)

    reranked.sort(key=lambda item: item["score"], reverse=True)
    return reranked[:n_results]


def hybrid_search(
    query: str,
    query_embedding: List[float],
    user_id: int,
    doc_ids: List[int],
    n_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid BM25 + vector search with RRF fusion.

    Args:
        query:          Raw user query string (for BM25).
        query_embedding: Dense embedding of the query (for vector search).
        user_id:        Current user's ID.
        doc_ids:        Document IDs to search within.
        n_results:      Number of final results to return.

    Returns:
        List of {text, filename, page_num, score} dicts.
    """
    if not doc_ids:
        return []

    expanded_query = expand_query_for_retrieval(query)

    # ── 1. Vector search ──────────────────────────────────────────────────────
    vector_results = vector_store.search(
        query_embedding=query_embedding,
        user_id=user_id,
        doc_ids=doc_ids,
        n_results=max(n_results * 3, 12),
    )
    logger.info("Vector search returned %d results.", len(vector_results))

    # ── 2. BM25 search ────────────────────────────────────────────────────────
    all_chunks = vector_store.get_all_chunks_for_docs(user_id=user_id, doc_ids=doc_ids)

    bm25_results: List[Dict[str, Any]] = []
    if all_chunks:
        corpus_texts = [c["text"] for c in all_chunks]
        tokenised_corpus = [_tokenize(t) for t in corpus_texts]
        bm25 = BM25Okapi(tokenised_corpus)

        query_tokens = _tokenize(expanded_query)
        scores = bm25.get_scores(query_tokens)

        # Pair each chunk with its BM25 score and sort
        scored = sorted(
            zip(all_chunks, scores), key=lambda x: x[1], reverse=True
        )
        for chunk, score in scored[:10]:
            bm25_results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "filename": chunk["filename"],
                    "page_num": chunk["page_num"],
                    "chunk_index": chunk.get("chunk_index", 0),
                    "section_heading": chunk.get("section_heading", ""),
                    "doc_id": chunk.get("doc_id", 0),
                    "score": float(score),
                    "bm25_score": float(score),
                }
            )
        logger.info("BM25 search returned %d results.", len(bm25_results))

    # ── 3. RRF Fusion ─────────────────────────────────────────────────────────
    fused = _reciprocal_rank_fusion([vector_results, bm25_results], key="chunk_id")
    logger.info("RRF fusion produced %d unique results.", len(fused))

    reranked = _rerank_results(expanded_query, fused, n_results)
    logger.info("Reranker kept %d results.", len(reranked))
    return reranked
