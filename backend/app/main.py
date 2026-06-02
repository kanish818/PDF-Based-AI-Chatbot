"""
FastAPI Application Entry Point
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import create_tables, engine
from app.api import auth, documents, chat
from app.services.document_processor import processor

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PDF AI Chatbot API",
    description="Upload PDFs and chat with them using AI (RAG + Groq LLM).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    logger.info("Starting PDF AI Chatbot backend …")

    # Ensure required directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info("Upload directory: %s", settings.UPLOAD_DIR)

    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    logger.info("ChromaDB directory: %s", settings.CHROMA_PERSIST_DIR)

    # Create DB tables
    create_tables()
    _ensure_document_columns()
    processor.start()

    logger.info("Startup complete. API docs at /docs")


@app.on_event("shutdown")
def on_shutdown():
    processor.stop()


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "PDF AI Chatbot API", "version": "1.0.0"}


def _ensure_document_columns() -> None:
    required_columns = {
        "storage_path": "TEXT",
        "processing_attempts": "INTEGER NOT NULL DEFAULT 0",
        "processing_started_at": "DATETIME",
        "processing_heartbeat_at": "DATETIME",
        "processing_error": "TEXT",
        "updated_at": "DATETIME",
    }

    with engine.begin() as connection:
        rows = connection.execute(text("PRAGMA table_info(documents)")).fetchall()
        existing_columns = {row[1] for row in rows}

        for column_name, column_sql in required_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f"ALTER TABLE documents ADD COLUMN {column_name} {column_sql}")
            )
            logger.info("Added missing documents.%s column.", column_name)

        connection.execute(
            text(
                """
                UPDATE documents
                SET updated_at = COALESCE(updated_at, created_at),
                    processing_attempts = COALESCE(processing_attempts, 0)
                """
            )
        )
