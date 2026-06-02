"""
Durable-ish document processing coordinator.

Jobs are persisted in the documents table and executed by a long-lived worker
thread so uploads are no longer tied to request-scoped BackgroundTasks.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_

from app.core.database import SessionLocal
from app.models.document import Document
from app.services import vector_store
from app.services.chunker import chunk_text
from app.services.embedder import embed_texts
from app.services.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)

HEARTBEAT_STALE_MINUTES = 10
MAX_PROCESSING_ATTEMPTS = 3


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentProcessor:
    def __init__(self) -> None:
        self._queue: "queue.Queue[int]" = queue.Queue()
        self._queued_ids: set[int] = set()
        self._queued_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.reconcile_stale_documents()
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="document-processor",
            daemon=True,
        )
        self._worker_thread.start()
        self.enqueue_pending_documents()
        logger.info("Document processor started.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        logger.info("Document processor stopped.")

    def enqueue(self, doc_id: int) -> None:
        with self._queued_lock:
            if doc_id in self._queued_ids:
                return
            self._queued_ids.add(doc_id)
        self._queue.put(doc_id)
        logger.info("Enqueued document id=%d for processing.", doc_id)

    def enqueue_pending_documents(self) -> None:
        db = SessionLocal()
        try:
            pending_docs = (
                db.query(Document)
                .filter(Document.status.in_(("queued", "processing")))
                .order_by(Document.created_at.asc())
                .all()
            )
            for doc in pending_docs:
                self.enqueue(doc.id)
        finally:
            db.close()

    def reconcile_stale_documents(self) -> None:
        db = SessionLocal()
        cutoff = utcnow() - timedelta(minutes=HEARTBEAT_STALE_MINUTES)
        try:
            stale_docs = (
                db.query(Document)
                .filter(Document.status.in_(("queued", "processing")))
                .filter(
                    or_(
                        Document.processing_heartbeat_at.is_(None),
                        Document.processing_heartbeat_at < cutoff,
                    )
                )
                .all()
            )
            for doc in stale_docs:
                if doc.processing_attempts >= MAX_PROCESSING_ATTEMPTS:
                    doc.status = "error"
                    doc.processing_error = (
                        "Document processing exceeded retry limit after restart recovery."
                    )
                else:
                    doc.status = "queued"
                    doc.processing_error = "Recovered after interrupted processing; retrying."
                doc.processing_started_at = None
                doc.processing_heartbeat_at = utcnow()
                doc.updated_at = utcnow()
            if stale_docs:
                db.commit()
                logger.warning("Recovered %d stale document jobs on startup.", len(stale_docs))
        finally:
            db.close()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                doc_id = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                self._process_document(doc_id)
            except Exception:
                logger.exception("Unhandled document processing failure for doc_id=%d", doc_id)
            finally:
                with self._queued_lock:
                    self._queued_ids.discard(doc_id)
                self._queue.task_done()

    def _heartbeat(self, db, doc: Document, *, error: Optional[str] = None) -> None:
        doc.processing_heartbeat_at = utcnow()
        doc.updated_at = utcnow()
        if error is not None:
            doc.processing_error = error[:1000]
        db.commit()

    def _process_document(self, doc_id: int) -> None:
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                logger.error("Document id=%d disappeared before processing started.", doc_id)
                return

            if doc.status == "ready":
                logger.info("Skipping already-ready doc_id=%d.", doc_id)
                return

            if not doc.storage_path or not os.path.exists(doc.storage_path):
                doc.status = "error"
                doc.processing_error = "Uploaded file is missing from disk; please re-upload it."
                doc.updated_at = utcnow()
                db.commit()
                logger.error("Document id=%d has no recoverable storage path.", doc_id)
                return

            doc.status = "processing"
            doc.processing_attempts = (doc.processing_attempts or 0) + 1
            doc.processing_started_at = utcnow()
            doc.processing_heartbeat_at = utcnow()
            doc.processing_error = None
            doc.updated_at = utcnow()
            db.commit()

            logger.info("Starting processing for doc_id=%d path=%s", doc.id, doc.storage_path)

            pages = parse_pdf(doc.storage_path, heartbeat=lambda: self._heartbeat(db, doc))
            page_count = len(pages)
            self._heartbeat(db, doc)

            chunks = chunk_text(pages, doc.filename)
            if not chunks:
                raise RuntimeError(
                    "No searchable text could be extracted from this PDF. Try a clearer file."
                )
            self._heartbeat(db, doc)

            texts = [chunk["text"] for chunk in chunks]
            embeddings = embed_texts(
                texts,
                task_type="RETRIEVAL_DOCUMENT",
                heartbeat=lambda: self._heartbeat(db, doc),
            )

            vector_store.delete_document(user_id=doc.user_id, doc_id=doc.id)
            vector_store.add_chunks(
                chunks=chunks,
                embeddings=embeddings,
                user_id=doc.user_id,
                doc_id=doc.id,
            )

            doc.page_count = page_count
            doc.status = "ready"
            doc.processing_error = None
            doc.processing_started_at = None
            doc.processing_heartbeat_at = utcnow()
            doc.updated_at = utcnow()
            db.commit()
            logger.info(
                "Document id=%d processed successfully (%d pages, %d chunks).",
                doc.id,
                page_count,
                len(chunks),
            )
        except Exception as exc:
            logger.error("Document processing failed for doc_id=%d: %s", doc_id, exc, exc_info=True)
            db.rollback()
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = "error"
                doc.processing_error = str(exc)[:1000]
                doc.processing_started_at = None
                doc.processing_heartbeat_at = utcnow()
                doc.updated_at = utcnow()
                db.commit()
        finally:
            db.close()


processor = DocumentProcessor()
