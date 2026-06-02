"""
Vector Store Service
Manages a ChromaDB persistent collection for storing and querying PDF chunk embeddings.
"""

import logging
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "pdf_documents"

# Singleton client / collection
_client: Optional[chromadb.PersistentClient] = None
_collection = None


def _get_collection():
    """Return (and lazily initialise) the ChromaDB collection."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection '%s' ready.", COLLECTION_NAME)
    return _collection


def add_chunks(
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
    user_id: int,
    doc_id: int,
) -> None:
    """
    Store chunk embeddings in ChromaDB.

    Args:
        chunks:     List of chunk dicts (must have 'text', 'filename', 'page_num', 'chunk_index').
        embeddings: Parallel list of embedding vectors.
        user_id:    Owner's user ID (stored as metadata for filtering).
        doc_id:     Document DB ID (stored as metadata for filtering).
    """
    collection = _get_collection()

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for chunk, embedding in zip(chunks, embeddings):
        chunk_index = chunk["chunk_index"]
        doc_id_str = f"{user_id}_{doc_id}_{chunk_index}"
        ids.append(doc_id_str)
        documents.append(chunk["text"])
        metadatas.append(
            {
                "chunk_id": doc_id_str,
                "filename": chunk["filename"],
                "page_num": chunk["page_num"],
                "chunk_index": chunk_index,
                "section_heading": chunk.get("section_heading", ""),
                "user_id": user_id,
                "doc_id": doc_id,
            }
        )

    if not ids:
        return

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    logger.info("Stored %d chunks for doc_id=%d, user_id=%d.", len(ids), doc_id, user_id)


def search(
    query_embedding: List[float],
    user_id: int,
    doc_ids: List[int],
    n_results: int = 10,
) -> List[Dict[str, Any]]:
    """
    Semantic vector search filtered to the given user and document IDs.

    Returns:
        List of dicts: {text, filename, page_num, score}
    """
    collection = _get_collection()

    if not doc_ids:
        return []

    # Build the ChromaDB where filter
    if len(doc_ids) == 1:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"doc_id": {"$eq": doc_ids[0]}},
            ]
        }
    else:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"doc_id": {"$in": doc_ids}},
            ]
        }

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.error("ChromaDB query failed: %s", exc)
        return []

    output: List[Dict[str, Any]] = []
    documents_list = results.get("documents", [[]])[0]
    metadatas_list = results.get("metadatas", [[]])[0]
    distances_list = results.get("distances", [[]])[0]

    for text, meta, distance in zip(documents_list, metadatas_list, distances_list):
        output.append(
            {
                "chunk_id": meta.get("chunk_id", ""),
                "text": text,
                "filename": meta.get("filename", ""),
                "page_num": meta.get("page_num", 0),
                "chunk_index": meta.get("chunk_index", 0),
                "section_heading": meta.get("section_heading", ""),
                "doc_id": meta.get("doc_id", 0),
                "score": 1.0 - distance,  # cosine similarity
                "vector_score": 1.0 - distance,
            }
        )

    return output


def get_all_chunks_for_docs(user_id: int, doc_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Retrieve ALL stored chunks for the given documents (used to build BM25 corpus).

    Returns:
        List of dicts: {text, filename, page_num}
    """
    collection = _get_collection()

    if not doc_ids:
        return []

    if len(doc_ids) == 1:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"doc_id": {"$eq": doc_ids[0]}},
            ]
        }
    else:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"doc_id": {"$in": doc_ids}},
            ]
        }

    try:
        results = collection.get(
            where=where_filter,
            include=["documents", "metadatas"],
        )
    except Exception as exc:
        logger.error("ChromaDB get failed: %s", exc)
        return []

    output: List[Dict[str, Any]] = []
    for text, meta in zip(results.get("documents", []), results.get("metadatas", [])):
        output.append(
            {
                "chunk_id": meta.get("chunk_id", ""),
                "text": text,
                "filename": meta.get("filename", ""),
                "page_num": meta.get("page_num", 0),
                "chunk_index": meta.get("chunk_index", 0),
                "section_heading": meta.get("section_heading", ""),
                "doc_id": meta.get("doc_id", 0),
            }
        )
    return output


def delete_document(user_id: int, doc_id: int) -> None:
    """Delete all ChromaDB chunks belonging to the given document."""
    collection = _get_collection()
    try:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"doc_id": {"$eq": doc_id}},
            ]
        }
        collection.delete(where=where_filter)
        logger.info("Deleted ChromaDB chunks for doc_id=%d, user_id=%d.", doc_id, user_id)
    except Exception as exc:
        logger.error("Failed to delete doc chunks from ChromaDB: %s", exc)
