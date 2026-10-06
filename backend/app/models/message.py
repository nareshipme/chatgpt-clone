import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ROLES = ("user", "assistant", "system")
STATUSES = ("streaming", "complete", "interrupted", "error")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Message(Base):
    """One message in a conversation.

    `parts` is a list of typed parts, e.g. [{"type": "text", "text": "..."}]. Today only text parts exist;
    tables, charts, images and action buttons are added later without a schema change.
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="role_valid"),
        CheckConstraint("status IN ('streaming', 'complete', 'interrupted', 'error')", name="status_valid"),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # JSONB on PostgreSQL (indexable, compact); plain JSON elsewhere (SQLite in tests).
    parts: Mapped[list] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="complete", server_default="complete")
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    @property
    def text(self) -> str:
        """Concatenated text of all text parts (what the model sees and what a plain export shows)."""
        return "".join(p.get("text", "") for p in self.parts if p.get("type") == "text")
