"""
Postgres-backed vector store using pgvector + SQLAlchemy.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.chunk import DocumentChunk, DocumentEmbedding

logger = logging.getLogger(__name__)


def add_chunks(
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
    user_id: int,
    doc_id: int,
) -> None:
    if not chunks:
        return

    db: Session = SessionLocal()
    try:
        created_chunks: List[DocumentChunk] = []
        for chunk in chunks:
            created = DocumentChunk(
                document_id=doc_id,
                user_id=user_id,
                chunk_index=chunk["chunk_index"],
                filename=chunk["filename"],
                page_num=chunk["page_num"],
                section_heading=chunk.get("section_heading", ""),
                text=chunk["text"],
            )
            db.add(created)
            created_chunks.append(created)
        db.flush()

        for chunk_row, embedding in zip(created_chunks, embeddings):
            db.add(
                DocumentEmbedding(
                    chunk_id=chunk_row.id,
                    document_id=doc_id,
                    user_id=user_id,
                    embedding=embedding,
                )
            )
        db.commit()
        logger.info("Stored %d Postgres chunks for doc_id=%d, user_id=%d.", len(chunks), doc_id, user_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def search(
    query_embedding: List[float],
    user_id: int,
    doc_ids: List[int],
    n_results: int = 10,
) -> List[Dict[str, Any]]:
    if not doc_ids:
        return []

    db: Session = SessionLocal()
    try:
        distance = DocumentEmbedding.embedding.cosine_distance(query_embedding)
        stmt = (
            select(DocumentChunk, distance.label("distance"))
            .join(DocumentEmbedding, DocumentEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentEmbedding.user_id == user_id)
            .where(DocumentEmbedding.document_id.in_(doc_ids))
            .order_by(distance.asc())
            .limit(n_results)
        )
        rows = db.execute(stmt).all()
        output: List[Dict[str, Any]] = []
        for chunk, raw_distance in rows:
            distance_value = float(raw_distance)
            output.append(
                {
                    "chunk_id": str(chunk.id),
                    "text": chunk.text,
                    "filename": chunk.filename,
                    "page_num": chunk.page_num,
                    "chunk_index": chunk.chunk_index,
                    "section_heading": chunk.section_heading or "",
                    "doc_id": chunk.document_id,
                    "score": 1.0 - distance_value,
                    "vector_score": 1.0 - distance_value,
                }
            )
        return output
    finally:
        db.close()


def get_all_chunks_for_docs(user_id: int, doc_ids: List[int]) -> List[Dict[str, Any]]:
    if not doc_ids:
        return []

    db: Session = SessionLocal()
    try:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.user_id == user_id)
            .where(DocumentChunk.document_id.in_(doc_ids))
            .order_by(DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "chunk_id": str(chunk.id),
                "text": chunk.text,
                "filename": chunk.filename,
                "page_num": chunk.page_num,
                "chunk_index": chunk.chunk_index,
                "section_heading": chunk.section_heading or "",
                "doc_id": chunk.document_id,
            }
            for chunk in rows
        ]
    finally:
        db.close()


def delete_document(user_id: int, doc_id: int) -> None:
    db: Session = SessionLocal()
    try:
        chunk_ids = db.execute(
            select(DocumentChunk.id)
            .where(DocumentChunk.user_id == user_id)
            .where(DocumentChunk.document_id == doc_id)
        ).scalars().all()
        if chunk_ids:
            db.query(DocumentEmbedding).filter(DocumentEmbedding.chunk_id.in_(chunk_ids)).delete(
                synchronize_session=False
            )
        db.query(DocumentChunk).filter(
            DocumentChunk.user_id == user_id,
            DocumentChunk.document_id == doc_id,
        ).delete(synchronize_session=False)
        db.commit()
        logger.info("Deleted Postgres chunks for doc_id=%d, user_id=%d.", doc_id, user_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
