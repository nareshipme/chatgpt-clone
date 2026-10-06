import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    """A chat thread owned by exactly one user. Every query must be scoped by user_id."""

    __tablename__ = "conversations"
    __table_args__ = (
        # Serves "list my conversations, newest activity first" and the keyset pagination over it.
        Index("ix_conversations_user_id_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New chat")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # Python-side defaults give microsecond precision on every database (SQLite's CURRENT_TIMESTAMP is per second);
    # the server defaults remain as a safety net for rows inserted outside the app.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=False
    )
