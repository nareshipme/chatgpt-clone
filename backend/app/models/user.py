import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('planner', 'manager', 'viewer')", name="role_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Stored lowercased by the service layer; the unique constraint makes duplicates impossible.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # The tenant and role come from this row on every request, never from anything the client sends.
    tenant_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("tenants.id"), nullable=False, default="northwind", server_default="northwind"
    )
    # planner: can approve actions; manager: same plus audit view; viewer: read-only.
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="planner", server_default="planner")
    # The chosen persona id, or NULL for the company's default. Validated against the catalog in the service.
    persona: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # never include the password hash
        return f"<User id={self.id} email={self.email!r}>"
