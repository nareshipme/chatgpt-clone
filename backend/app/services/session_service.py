"""Refresh-token lifecycle: issue, rotate (with reuse detection) and revoke."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import UnauthorizedError
from app.models import RefreshToken


class InvalidRefreshTokenError(UnauthorizedError):
    code, default_message = "invalid_refresh_token", "Invalid or expired refresh token"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; PostgreSQL returns aware ones. Normalize to UTC-aware."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def issue(session: AsyncSession, user_id: uuid.UUID, *, family_id: uuid.UUID | None = None) -> str:
    """Create a refresh token and return the raw value (shown once; only its hash is stored)."""
    raw = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id or uuid.uuid4(),
            token_hash=_hash(raw),
            expires_at=_now() + timedelta(days=settings.refresh_token_days),
        )
    )
    await session.flush()
    return raw


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def rotate(session: AsyncSession, raw: str) -> tuple[uuid.UUID, str]:
    """Exchange a valid refresh token for a new one. Returns (user_id, new_raw_token).

    The old token is claimed with an atomic UPDATE ... WHERE revoked_at IS NULL, so two concurrent
    requests with the same token cannot both succeed. Presenting an already-used token means it was
    probably stolen: the whole session family is revoked.
    """
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if row is None:
        raise InvalidRefreshTokenError()
    if _aware(row.expires_at) <= _now():
        raise InvalidRefreshTokenError()

    claimed = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    if claimed.rowcount == 0:  # already used or revoked: treat as reuse
        await _revoke_family(session, row.family_id)
        await session.commit()
        raise InvalidRefreshTokenError("Refresh token reuse detected; session revoked")

    new_raw = await issue(session, row.user_id, family_id=row.family_id)
    await session.commit()
    return row.user_id, new_raw


async def revoke(session: AsyncSession, raw: str | None) -> None:
    """Logout: revoke the whole session family for this token. Idempotent; unknown tokens are ignored."""
    if not raw:
        return
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if row is not None:
        await _revoke_family(session, row.family_id)
        await session.commit()
