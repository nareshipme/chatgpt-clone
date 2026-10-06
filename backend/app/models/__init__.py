"""SQLAlchemy models. Import every model module here so Alembic autogenerate sees them."""
from app.models.user import User

__all__ = ["User"]
