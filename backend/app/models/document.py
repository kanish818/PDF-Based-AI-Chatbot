from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False, default=0)
    page_count = Column(Integer, nullable=True, default=0)
    status = Column(String, nullable=False, default="processing")  # processing | ready | error
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
