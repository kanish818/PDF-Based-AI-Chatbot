"""
Documents Router
Handles PDF upload, listing, and deletion. Processing is queued via the
document processor service so work survives request completion.
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.document import Document
from app.models.user import User
from app.services.document_processor import processor
from app.services.supabase_storage import storage_service
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
    processing_error: Optional[str] = None
    summary_text: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.post("/upload", response_model=List[DocumentOut], status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload one or more PDF files. Each file is saved to Supabase Storage and processed
    asynchronously (parse → embed → store). Returns document records immediately
    with status='queued'.
    """
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

        object_key = f"{current_user.id}/{uuid.uuid4().hex}_{upload_file.filename}"
        try:
            storage_service.upload_bytes(object_key, content, upload_file.content_type or "application/pdf")
        except Exception as exc:
            logger.error("Failed to upload PDF to Supabase Storage: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not store the uploaded PDF. Please try again.",
            ) from exc

        # Create DB record
        doc = Document(
            user_id=current_user.id,
            filename=upload_file.filename,
            storage_path=object_key,
            storage_bucket=settings.SUPABASE_STORAGE_BUCKET,
            file_size=file_size,
            status="queued",
            page_count=0,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        processor.enqueue(doc.id)

        created_docs.append(doc)
        logger.info("Queued doc_id=%d '%s' for processing.", doc.id, upload_file.filename)

    return [
        DocumentOut(
            id=d.id,
            filename=d.filename,
            file_size=d.file_size,
            page_count=d.page_count,
            status=d.status,
            processing_error=d.processing_error,
            summary_text=d.summary_text,
            created_at=d.created_at.isoformat() if d.created_at else "",
            updated_at=d.updated_at.isoformat() if d.updated_at else "",
        )
        for d in created_docs
    ]


@router.get("/", response_model=List[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all documents belonging to the current user."""
    # Only ensure the worker thread is alive — don't run full reconciliation on every poll.
    processor.ensure_running()
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
            processing_error=d.processing_error,
            summary_text=d.summary_text,
            created_at=d.created_at.isoformat() if d.created_at else "",
            updated_at=d.updated_at.isoformat() if d.updated_at else "",
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

    if doc.storage_path:
        try:
            storage_service.delete_object(doc.storage_path)
        except Exception as exc:
            logger.warning("Could not remove file for doc_id=%d: %s", doc_id, exc)

    # Remove from DB
    db.delete(doc)
    db.commit()
    logger.info("Deleted document id=%d for user id=%d.", doc_id, current_user.id)
