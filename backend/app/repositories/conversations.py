"""Conversation queries. Every function takes user_id: there is deliberately no way to fetch a
conversation without saying whose it is, so one user can never reach another user's rows."""
import uuid
from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation


def _escape_like(term: str) -> str:
    """Make %, _ and \\ literal inside a LIKE pattern."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def add(session: AsyncSession, *, user_id: uuid.UUID, title: str) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title)
    session.add(conversation)
    await session.flush()
    return conversation


async def get_owned(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
    return await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )


async def list_page(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    after: tuple[datetime, uuid.UUID] | None = None,
    q: str | None = None,
    archived: bool = False,
) -> list[Conversation]:
    """Newest activity first. `after` is the (updated_at, id) of the last row already seen (keyset pagination)."""
    stmt = select(Conversation).where(Conversation.user_id == user_id, Conversation.archived == archived)
    if q:
        pattern = f"%{_escape_like(q.lower())}%"
        stmt = stmt.where(func.lower(Conversation.title).like(pattern, escape="\\"))
    if after is not None:
        stmt = stmt.where(tuple_(Conversation.updated_at, Conversation.id) < tuple_(*after))
    stmt = stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


async def delete(session: AsyncSession, conversation: Conversation) -> None:
    await session.delete(conversation)
