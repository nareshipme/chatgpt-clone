import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ACTION_STATUSES = ("proposed", "approved", "dismissed", "expired")
_JSON = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProposedAction(Base):
    """Something the copilot suggests doing. The button in the chat only carries this row's id: what would actually
    happen (type and payload) lives here on the server, so a client can never approve something it made up."""

    __tablename__ = "proposed_actions"
    __table_args__ = (
        CheckConstraint("status IN ('proposed', 'approved', 'dismissed', 'expired')", name="status_valid"),
        Index("ix_proposed_actions_tenant_id_created_at", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(40), ForeignKey("tenants.id"), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    proposed_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    payload: Mapped[dict] = mapped_column(_JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="proposed", server_default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(_JSON, nullable=True)


class AuditEvent(Base):
    """Append-only record of who did what, when. There is deliberately no update or delete code for this table."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_tenant_id_created_at", "tenant_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(40), ForeignKey("tenants.id"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(_JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
