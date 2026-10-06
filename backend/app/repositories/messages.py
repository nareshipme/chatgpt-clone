"""Message queries. Reads join through conversations so they are always scoped to the owning user."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message


async def add(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    role: str,
    parts: list[dict],
    status: str = "complete",
    created_at: datetime | None = None,
) -> Message:
    message = Message(conversation_id=conversation_id, role=role, parts=parts, status=status)
    if created_at is not None:
        message.created_at = created_at
    session.add(message)
    await session.flush()
    return message


async def list_for_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID, *, limit: int | None = None
) -> list[Message]:
    """Oldest first. Joins conversations on user_id, so another user's thread simply returns no rows."""
    stmt = (
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.conversation_id == conversation_id, Conversation.user_id == user_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await session.scalars(stmt)).all())


async def get_owned(session: AsyncSession, user_id: uuid.UUID, message_id: uuid.UUID) -> Message | None:
    return await session.scalar(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.id == message_id, Conversation.user_id == user_id)
    )


async def has_active_stream(session: AsyncSession, conversation_id: uuid.UUID, *, max_age: timedelta) -> bool:
    """True if an assistant reply is currently streaming. Rows older than max_age are treated as abandoned
    (a server restart can leave a row stuck in 'streaming'); they must not block the conversation forever."""
    cutoff = datetime.now(timezone.utc) - max_age
    found = await session.scalar(
        select(Message.id)
        .where(
            Message.conversation_id == conversation_id,
            Message.status == "streaming",
            Message.created_at > cutoff,
        )
        .limit(1)
    )
    return found is not None


async def has_any(session: AsyncSession, conversation_id: uuid.UUID) -> bool:
    return (await session.scalar(select(Message.id).where(Message.conversation_id == conversation_id).limit(1))) is not None
