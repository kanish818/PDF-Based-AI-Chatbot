"""
Chat Router
Manages conversations and provides SSE streaming chat via hybrid RAG.
"""

import json
import logging
import re
from typing import List, Optional, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.conversation import Conversation, ConversationDocument, Message
from app.models.document import Document
from app.models.user import User
from app.services.embedder import embed_query
from app.services.retriever import choose_retrieval_count, hybrid_search
from app.services.llm import stream_chat

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    document_ids: Optional[List[int]] = []


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: str
    message_count: int
    document_ids: List[int] = []


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[List[dict]] = None
    created_at: str


class StreamRequest(BaseModel):
    question: str
    document_ids: List[int] = []


# ── Helper ─────────────────────────────────────────────────────────────────────


def _parse_sources(sources_json: Optional[str]) -> Optional[List[dict]]:
    if not sources_json:
        return None
    try:
        return json.loads(sources_json)
    except (json.JSONDecodeError, TypeError):
        return None


def _get_conversation_or_404(conv_id: int, user_id: int, db: Session) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == user_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conv


def _get_conversation_document_ids(conv_id: int, db: Session) -> List[int]:
    rows = (
        db.query(ConversationDocument.document_id)
        .filter(ConversationDocument.conversation_id == conv_id)
        .all()
    )
    return [row.document_id for row in rows]


def _persist_conversation_document_ids(conv_id: int, doc_ids: List[int], db: Session) -> List[int]:
    existing = set(_get_conversation_document_ids(conv_id, db))
    missing = [doc_id for doc_id in doc_ids if doc_id not in existing]
    if missing:
        db.add_all(
            [
                ConversationDocument(conversation_id=conv_id, document_id=doc_id)
                for doc_id in missing
            ]
        )
        db.commit()
    return _get_conversation_document_ids(conv_id, db)


def _unique_doc_ids(doc_ids: Optional[List[int]]) -> List[int]:
    return list(dict.fromkeys(doc_ids or []))


def _normalise_label(value: str) -> str:
    value = value.rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _infer_conversation_document_ids(conv: Conversation, user_id: int, db: Session) -> List[int]:
    linked = _get_conversation_document_ids(conv.id, db)
    if linked:
        return linked

    docs = (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.status == "ready")
        .all()
    )
    if not docs:
        return []

    normalised_title = _normalise_label(conv.title or "")
    if normalised_title:
        exact_matches = [
            doc.id for doc in docs if _normalise_label(doc.filename) == normalised_title
        ]
        if len(exact_matches) == 1:
            return _persist_conversation_document_ids(conv.id, exact_matches, db)

        fuzzy_matches = [
            doc.id
            for doc in docs
            if normalised_title in _normalise_label(doc.filename)
            or _normalise_label(doc.filename) in normalised_title
        ]
        fuzzy_matches = list(dict.fromkeys(fuzzy_matches))
        if len(fuzzy_matches) == 1:
            return _persist_conversation_document_ids(conv.id, fuzzy_matches, db)

    source_doc_ids = set()
    source_filename_to_id = {doc.filename: doc.id for doc in docs}
    assistant_rows = (
        db.query(Message.sources)
        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
        .all()
    )
    for row in assistant_rows:
        parsed_sources = _parse_sources(row.sources)
        if not parsed_sources:
            continue
        for source in parsed_sources:
            filename = source.get("filename")
            if filename in source_filename_to_id:
                source_doc_ids.add(source_filename_to_id[filename])

    if len(source_doc_ids) == 1:
        return _persist_conversation_document_ids(conv.id, list(source_doc_ids), db)

    if len(docs) == 1:
        return _persist_conversation_document_ids(conv.id, [docs[0].id], db)

    return []


def _get_allowed_documents(user_id: int, doc_ids: List[int], db: Session) -> List[Document]:
    if not doc_ids:
        return []
    return (
        db.query(Document)
        .filter(
            Document.user_id == user_id,
            Document.status == "ready",
            Document.id.in_(doc_ids),
        )
        .all()
    )


def _build_chat_history(
    conv_id: int,
    allowed_docs: List[Document],
    newest_message_id: int,
    db: Session,
) -> List[dict]:
    allowed_filenames = {doc.filename for doc in allowed_docs}
    history_rows = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id, Message.id != newest_message_id)
        .order_by(Message.created_at.asc())
        .limit(12)
        .all()
    )

    safe_history: List[dict] = []
    for msg in history_rows:
        if msg.role == "user":
            safe_history.append({"role": msg.role, "content": msg.content})
            continue

        parsed_sources = _parse_sources(msg.sources)
        if not parsed_sources:
            continue

        source_filenames = {
            source.get("filename", "")
            for source in parsed_sources
            if source.get("filename")
        }
        if source_filenames and source_filenames.issubset(allowed_filenames):
            safe_history.append({"role": msg.role, "content": msg.content})

    return safe_history[-10:]


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all conversations for the current user with message counts."""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    result: List[ConversationOut] = []
    for conv in convs:
        count = db.query(Message).filter(Message.conversation_id == conv.id).count()
        document_ids = _infer_conversation_document_ids(conv, current_user.id, db)
        result.append(
            ConversationOut(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at.isoformat() if conv.created_at else "",
                message_count=count,
                document_ids=document_ids,
            )
        )
    return result


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation."""
    doc_ids = _unique_doc_ids(payload.document_ids)

    if doc_ids:
        owned_docs = _get_allowed_documents(current_user.id, doc_ids, db)
        owned_ids = {doc.id for doc in owned_docs}
        invalid = [doc_id for doc_id in doc_ids if doc_id not in owned_ids]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Document IDs not found, not ready, or not owned by user: {invalid}",
            )

    conv = Conversation(user_id=current_user.id, title=payload.title or "New Conversation")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    if doc_ids:
        db.add_all(
            [
                ConversationDocument(conversation_id=conv.id, document_id=doc_id)
                for doc_id in doc_ids
            ]
        )
        db.commit()

    logger.info("Created conversation id=%d for user id=%d.", conv.id, current_user.id)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat() if conv.created_at else "",
        message_count=0,
        document_ids=doc_ids,
    )


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    conv = _get_conversation_or_404(conv_id, current_user.id, db)
    db.query(ConversationDocument).filter(ConversationDocument.conversation_id == conv_id).delete()
    db.query(Message).filter(Message.conversation_id == conv_id).delete()
    db.delete(conv)
    db.commit()
    logger.info("Deleted conversation id=%d.", conv_id)


@router.get("/conversations/{conv_id}/messages", response_model=List[MessageOut])
def get_messages(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all messages in a conversation."""
    _get_conversation_or_404(conv_id, current_user.id, db)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            sources=_parse_sources(m.sources),
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in messages
    ]


@router.post("/conversations/{conv_id}/stream")
async def stream_conversation(
    conv_id: int,
    payload: StreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    SSE streaming endpoint.
    Saves user message → embeds query → hybrid retrieval → streams Groq response
    → saves assistant message → emits sources and done events.

    SSE events:
      data: {"type": "chunk",   "content": "..."}
      data: {"type": "sources", "sources": [...]}
      data: {"type": "done"}
    """
    _get_conversation_or_404(conv_id, current_user.id, db)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question is empty.")

    conv = _get_conversation_or_404(conv_id, current_user.id, db)
    scoped_doc_ids = _infer_conversation_document_ids(conv, current_user.id, db)
    requested_doc_ids = _unique_doc_ids(payload.document_ids)

    if scoped_doc_ids:
        doc_ids = scoped_doc_ids
        if requested_doc_ids and requested_doc_ids != doc_ids:
            logger.warning(
                "Ignoring payload document_ids=%s for conversation id=%d; locked scope is %s.",
                requested_doc_ids,
                conv_id,
                doc_ids,
            )
    else:
        doc_ids = requested_doc_ids
        if doc_ids:
            doc_ids = _persist_conversation_document_ids(conv_id, doc_ids, db)

    allowed_docs = _get_allowed_documents(current_user.id, doc_ids, db)
    allowed_doc_ids = {doc.id for doc in allowed_docs}
    invalid = [doc_id for doc_id in doc_ids if doc_id not in allowed_doc_ids]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Document IDs not found, not ready, or not owned by user: {invalid}",
        )

    # Save the user message to DB now (before streaming)
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    chat_history = _build_chat_history(
        conv_id=conv_id,
        allowed_docs=allowed_docs,
        newest_message_id=user_msg.id,
        db=db,
    )

    # Snapshot IDs and user_id before closing over them in the generator
    user_id = current_user.id

    async def event_generator() -> AsyncGenerator[str, None]:
        if not doc_ids:
            response_text = (
                "I couldn't determine which PDF this older conversation is linked to. "
                "Start a new conversation and select the intended document again."
            )
            event = json.dumps({"type": "chunk", "content": response_text})
            yield f"data: {event}\n\n"

            from app.core.database import SessionLocal

            save_db = SessionLocal()
            try:
                assistant_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=response_text,
                    sources=None,
                )
                save_db.add(assistant_msg)
                save_db.commit()
            finally:
                save_db.close()

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Embed the query
        try:
            query_embedding = embed_query(question)
        except Exception as exc:
            logger.error("Embedding query failed: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
            return

        # Hybrid retrieval
        retrieved_chunks = []
        if doc_ids:
            try:
                retrieved_chunks = hybrid_search(
                    query=question,
                    query_embedding=query_embedding,
                    user_id=user_id,
                    doc_ids=doc_ids,
                    n_results=choose_retrieval_count(question),
                )
            except Exception as exc:
                logger.error("Retrieval failed: %s", exc)

        # Stream LLM response
        full_response = ""
        try:
            for text_chunk in stream_chat(
                question=question,
                context_chunks=retrieved_chunks,
                chat_history=chat_history,
            ):
                full_response += text_chunk
                event = json.dumps({"type": "chunk", "content": text_chunk})
                yield f"data: {event}\n\n"
        except Exception as exc:
            logger.error("LLM streaming error: %s", exc)
            error_event = json.dumps({"type": "error", "content": str(exc)})
            yield f"data: {error_event}\n\n"
            return

        # Prepare sources for client and DB (include text excerpt)
        sources_list = [
            {
                "filename": c.get("filename", ""),
                "page_num": c.get("page_num", 0),
                "text": c.get("text", "")[:400],  # excerpt capped at 400 chars
            }
            for c in retrieved_chunks
        ]

        # Save assistant message to DB
        # We need a new session here since the request session may be closed
        from app.core.database import SessionLocal
        save_db = SessionLocal()
        try:
            assistant_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=full_response,
                sources=json.dumps(sources_list) if sources_list else None,
            )
            save_db.add(assistant_msg)
            save_db.commit()
        except Exception as exc:
            logger.error("Failed to save assistant message: %s", exc)
        finally:
            save_db.close()

        # Emit sources and done events
        if sources_list:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources_list})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
