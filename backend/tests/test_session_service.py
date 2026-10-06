import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models import RefreshToken
from app.services import auth_service, session_service
from app.services.session_service import InvalidRefreshTokenError


@pytest.fixture
async def session(migrated_db):
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def user(session):
    return await auth_service.register(session, email="u@example.com", password="a-long-enough-pw", display_name="U")


async def _rows(session):
    return list((await session.scalars(select(RefreshToken).order_by(RefreshToken.created_at))).all())


async def test_issue_stores_only_a_hash(session, user):
    raw = await session_service.issue(session, user.id)
    await session.commit()
    (row,) = await _rows(session)
    assert row.token_hash != raw and len(row.token_hash) == 64
    assert raw not in row.token_hash


async def test_rotate_returns_a_new_token_and_revokes_the_old_one(session, user):
    first = await session_service.issue(session, user.id)
    await session.commit()
    user_id, second = await session_service.rotate(session, first)
    assert user_id == user.id and second != first
    old, new = await _rows(session)
    assert old.revoked_at is not None and new.revoked_at is None
    assert old.family_id == new.family_id  # same login session


async def test_reusing_a_rotated_token_revokes_the_whole_family(session, user):
    first = await session_service.issue(session, user.id)
    await session.commit()
    _, second = await session_service.rotate(session, first)
    with pytest.raises(InvalidRefreshTokenError):
        await session_service.rotate(session, first)  # the attacker replays the old token
    assert all(r.revoked_at is not None for r in await _rows(session))
    with pytest.raises(InvalidRefreshTokenError):  # so the legitimate user's newest token is dead too
        await session_service.rotate(session, second)


async def test_expired_token_is_rejected(session, user, monkeypatch):
    monkeypatch.setattr(settings, "refresh_token_days", -1)
    raw = await session_service.issue(session, user.id)
    await session.commit()
    with pytest.raises(InvalidRefreshTokenError):
        await session_service.rotate(session, raw)


async def test_unknown_token_is_rejected(session):
    with pytest.raises(InvalidRefreshTokenError):
        await session_service.rotate(session, "never-issued")


async def test_logout_revokes_the_session_and_is_idempotent(session, user):
    raw = await session_service.issue(session, user.id)
    await session.commit()
    await session_service.revoke(session, raw)
    await session_service.revoke(session, raw)  # second call is a no-op
    await session_service.revoke(session, None)
    await session_service.revoke(session, "unknown")
    with pytest.raises(InvalidRefreshTokenError):
        await session_service.rotate(session, raw)


async def test_separate_logins_get_separate_families(session, user):
    await session_service.issue(session, user.id)
    await session_service.issue(session, user.id)
    await session.commit()
    a, b = await _rows(session)
    assert a.family_id != b.family_id
