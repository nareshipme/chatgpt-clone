import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.repositories import messages as repo
from app.services import conversation_service

MAX_USER_MESSAGE_CHARS = 8000


def text_parts(text: str) -> list[dict]:
    return [{"type": "text", "text": text}]


async def list_messages(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[Message]:
    # get() raises ConversationNotFoundError (404) for a conversation that is not the caller's.
    await conversation_service.get(session, user_id, conversation_id)
    return await repo.list_for_conversation(session, user_id, conversation_id)


async def add_message(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    role: str,
    text: str = "",
    status: str = "complete",
) -> Message:
    """Append a message to one of the caller's conversations and bump the conversation's activity time."""
    conversation = await conversation_service.get(session, user_id, conversation_id)
    message = await repo.add(
        session, conversation_id=conversation.id, role=role, parts=text_parts(text), status=status
    )
    conversation.updated_at = datetime.now(timezone.utc)  # newest activity floats to the top of the sidebar
    await session.flush()
    return message
