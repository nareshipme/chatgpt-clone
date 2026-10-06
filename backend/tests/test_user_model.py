import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import User


@pytest.fixture
async def session(migrated_db):
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


async def test_user_defaults_are_populated(session):
    user = User(email="a@example.com", password_hash="hash", display_name="A")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert isinstance(user.id, uuid.UUID)
    assert user.created_at is not None and user.updated_at is not None


async def test_duplicate_email_is_rejected(session):
    session.add(User(email="dup@example.com", password_hash="h", display_name="One"))
    await session.commit()
    session.add(User(email="dup@example.com", password_hash="h", display_name="Two"))
    with pytest.raises(IntegrityError):
        await session.commit()


def test_repr_does_not_leak_password_hash():
    user = User(email="a@example.com", password_hash="super-secret-hash", display_name="A")
    assert "super-secret-hash" not in repr(user)
