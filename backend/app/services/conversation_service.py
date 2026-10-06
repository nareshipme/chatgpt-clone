import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, NotFoundError
from app.models import Conversation
from app.repositories import conversations as repo

DEFAULT_TITLE = "New chat"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


class ConversationNotFoundError(NotFoundError):
    # 404 (not 403) for other users' conversations: do not reveal that the id exists.
    code, default_message = "conversation_not_found", "Conversation not found"


class InvalidCursorError(AppError):
    status_code, code, default_message = 400, "invalid_cursor", "Invalid pagination cursor"


@dataclass
class Page:
    items: list[Conversation]
    next_cursor: str | None


def encode_cursor(updated_at: datetime, conversation_id: uuid.UUID) -> str:
    raw = f"{updated_at.isoformat()}|{conversation_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        stamp, _, ident = raw.partition("|")
        return datetime.fromisoformat(stamp), uuid.UUID(ident)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise InvalidCursorError() from None


def _clean_title(title: str | None) -> str:
    return (title or "").strip()[:200] or DEFAULT_TITLE


async def create(session: AsyncSession, user_id: uuid.UUID, title: str | None = None) -> Conversation:
    conversation = await repo.add(session, user_id=user_id, title=_clean_title(title))
    await session.commit()
    return conversation


async def get(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = await repo.get_owned(session, user_id, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError()
    return conversation


async def list_page(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    q: str | None = None,
    archived: bool = False,
) -> Page:
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    after = decode_cursor(cursor) if cursor else None
    rows = await repo.list_page(session, user_id, limit=limit + 1, after=after, q=q.strip() if q else None, archived=archived)
    has_more = len(rows) > limit  # we asked for one extra row just to know whether another page exists
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1].updated_at, items[-1].id) if has_more else None
    return Page(items=items, next_cursor=next_cursor)


async def update(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    title: str | None = None,
    archived: bool | None = None,
) -> Conversation:
    conversation = await get(session, user_id, conversation_id)
    if title is not None:
        conversation.title = _clean_title(title)
    if archived is not None:
        conversation.archived = archived
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def delete(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
    conversation = await get(session, user_id, conversation_id)
    await repo.delete(session, conversation)
    await session.commit()
