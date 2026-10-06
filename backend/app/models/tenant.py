from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tenant(Base):
    """A fictional customer company. Everything the copilot reads or writes is scoped to one tenant."""

    __tablename__ = "tenants"

    # A readable slug ('northwind') rather than a UUID: scenario data and audit rows refer to it constantly.
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(60), nullable=False)
