from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=False, default=0)
    page_count = Column(Integer, nullable=True, default=0)
    status = Column(String, nullable=False, default="queued")  # queued | processing | ready | error
    processing_attempts = Column(Integer, nullable=False, default=0)
    processing_started_at = Column(DateTime, nullable=True)
    processing_heartbeat_at = Column(DateTime, nullable=True)
    processing_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
