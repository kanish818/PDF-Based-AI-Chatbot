"""
Documents Router
Handles PDF upload, listing, and deletion. Processing runs as a background task.
"""

import logging
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.document import Document
from app.models.user import User
from app.services.pdf_parser import parse_pdf
from app.services.chunker import chunk_text
from app.services.embedder import embed_texts
from app.services import vector_store

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_size: int
    page_count: Optional[int] = None
    status: str
    created_at: str

    model_config = {"from_attributes": True}


# ── Background processing ──────────────────────────────────────────────────────


def _process_document(file_path: str, doc_id: int, user_id: int) -> None:
    """
    Background task: parse → chunk → embed → store in ChromaDB → update DB status.
    Uses its own DB session (background tasks run outside request scope).
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error("Background task: document id=%d not found.", doc_id)
            return

        logger.info("Starting processing for doc_id=%d path=%s", doc_id, file_path)

        # Parse
        pages = parse_pdf(file_path)
        page_count = len(pages)
        logger.info("Parsed %d pages for doc_id=%d.", page_count, doc_id)

        # Chunk
        filename = doc.filename
        chunks = chunk_text(pages, filename)
        if not chunks:
            raise RuntimeError(
                "No searchable text could be extracted. Try a clearer PDF or enable OCR."
            )

        logger.info("Created %d chunks for doc_id=%d. Starting embedding…", len(chunks), doc_id)

        # Embed — this is the slow step (API calls)
        texts = [c["text"] for c in chunks]
        embeddings = embed_texts(texts, task_type="retrieval_document")

        # Store in ChromaDB
        vector_store.add_chunks(
            chunks=chunks,
            embeddings=embeddings,
            user_id=user_id,
            doc_id=doc_id,
        )

        # Mark ready
        doc.page_count = page_count
        doc.status = "ready"
        db.commit()
        logger.info(
            "Document id=%d processed successfully (%d pages, %d chunks).",
            doc_id, page_count, len(chunks),
        )

    except Exception as exc:
        logger.error("Document processing failed for doc_id=%d: %s", doc_id, exc, exc_info=True)
        try:
            # Re-fetch in case session state is dirty
            doc2 = db.query(Document).filter(Document.id == doc_id).first()
            if doc2:
                doc2.status = "error"
                db.commit()
        except Exception as db_exc:
            logger.error("Could not mark doc_id=%d as error: %s", doc_id, db_exc)
    finally:
        db.close()


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.post("/upload", response_model=List[DocumentOut], status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload one or more PDF files. Each file is saved to disk and processed
    asynchronously (parse → embed → store). Returns document records immediately
    with status='processing'.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    created_docs: List[Document] = []

    for upload_file in files:
        # Validate file type
        if not upload_file.filename or not upload_file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{upload_file.filename}' is not a PDF.",
            )

        # Read content and validate size
        content = await upload_file.read()
        file_size = len(content)

        if file_size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File '{upload_file.filename}' exceeds the "
                    f"{settings.MAX_UPLOAD_SIZE_MB}MB limit."
                ),
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{upload_file.filename}' is empty.",
            )

        # Save to disk with a unique name to avoid collisions
        unique_name = f"{uuid.uuid4().hex}_{upload_file.filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_name)
        with open(file_path, "wb") as f:
            f.write(content)

        # Create DB record
        doc = Document(
            user_id=current_user.id,
            filename=upload_file.filename,
            file_size=file_size,
            status="processing",
            page_count=0,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Enqueue background processing
        background_tasks.add_task(
            _process_document,
            file_path=file_path,
            doc_id=doc.id,
            user_id=current_user.id,
        )

        created_docs.append(doc)
        logger.info("Queued doc_id=%d '%s' for processing.", doc.id, upload_file.filename)

    return [
        DocumentOut(
            id=d.id,
            filename=d.filename,
            file_size=d.file_size,
            page_count=d.page_count,
            status=d.status,
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in created_docs
    ]


@router.get("/", response_model=List[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all documents belonging to the current user."""
    docs = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [
        DocumentOut(
            id=d.id,
            filename=d.filename,
            file_size=d.file_size,
            page_count=d.page_count,
            status=d.status,
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in docs
    ]


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a document from the DB and remove its vectors from ChromaDB."""
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Remove from vector store
    vector_store.delete_document(user_id=current_user.id, doc_id=doc_id)

    # Remove from DB
    db.delete(doc)
    db.commit()
    logger.info("Deleted document id=%d for user id=%d.", doc_id, current_user.id)
