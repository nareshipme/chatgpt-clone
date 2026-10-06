import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def add(session: AsyncSession, *, email: str, password_hash: str, display_name: str) -> User:
    """Stage a new user and flush so defaults (id, timestamps) are populated. The caller commits."""
    user = User(email=email, password_hash=password_hash, display_name=display_name)
    session.add(user)
    await session.flush()
    return user
