"""
FastAPI Application Entry Point
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import create_tables, engine, DATABASE_URL
from app.api import auth, documents, chat
from app.services.document_processor import processor
from app.services.supabase_storage import storage_service

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

    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    logger.info("Temp directory: %s", settings.TEMP_DIR)

    # Create DB tables
    create_tables()
    _ensure_document_columns()
    if storage_service.is_configured():
        storage_service.ensure_bucket()
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
        "storage_bucket": "TEXT",
        "processing_attempts": "INTEGER NOT NULL DEFAULT 0",
        "processing_started_at": "DATETIME",
        "processing_heartbeat_at": "DATETIME",
        "processing_error": "TEXT",
        "summary_text": "TEXT",
        "document_type": "TEXT",
        "main_topics_json": "TEXT",
        "people_names_json": "TEXT",
        "updated_at": "DATETIME",
    }

    with engine.begin() as connection:
        inspector = inspect(connection)
        existing_columns = {col["name"] for col in inspector.get_columns("documents")}
        is_sqlite = DATABASE_URL.startswith("sqlite")

        for column_name, column_sql in required_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f"ALTER TABLE documents ADD COLUMN {column_name} {column_sql}")
            )
            logger.info("Added missing documents.%s column.", column_name)

        if is_sqlite:
            connection.execute(
                text(
                    """
                    UPDATE documents
                    SET updated_at = COALESCE(updated_at, created_at),
                        processing_attempts = COALESCE(processing_attempts, 0)
                    """
                )
            )
        else:
            connection.execute(
                text(
                    """
                    UPDATE documents
                    SET updated_at = COALESCE(updated_at, created_at),
                        processing_attempts = COALESCE(processing_attempts, 0),
                        storage_bucket = COALESCE(storage_bucket, :bucket)
                    """
                ),
                {"bucket": settings.SUPABASE_STORAGE_BUCKET},
            )
