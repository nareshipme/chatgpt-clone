"""One chat turn: save the user's message, stream the model's reply, save the reply.

Design notes (the parts worth being able to explain):
- prepare_turn runs BEFORE the response starts, so a missing conversation (404), a busy conversation (409)
  or invalid input are ordinary JSON errors, not half-open streams.
- The stream opens its own database sessions: it outlives the request-scoped session.
- A producer task reads the model and feeds a queue; the consumer yields SSE frames. That lets us send a
  heartbeat during silent waits without cancelling the model call, and cancel the model cleanly on Stop.
- Whatever happens (done, model error, client disconnect), the assistant row ends in a terminal status
  (complete / error / interrupted), written under a cancellation shield so a closed tab cannot leave it
  stuck in 'streaming'.
"""
import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import anyio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.errors import ConflictError
from app.llm.base import ChatMessage, LLMError, LLMProvider, TextDelta, Usage
from app.models import Conversation, Message
from app.repositories import messages as repo
from app.services import conversation_service
from app.services.message_service import text_parts

log = logging.getLogger("app.chat")

SYSTEM_PROMPT = "You are a helpful, concise assistant."
HEARTBEAT_SECONDS = 15.0
STREAM_STALE_AFTER = timedelta(minutes=5)
TITLE_MAX_CHARS = 60

_DONE = object()


class StreamInProgressError(ConflictError):
    code, default_message = "stream_in_progress", "A reply is already being generated for this conversation."


@dataclass(frozen=True)
class Turn:
    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID
    history: list[ChatMessage]


def sse(event: str, data: dict) -> str:
    """One Server-Sent Events frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def title_from(text: str) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= TITLE_MAX_CHARS else one_line[: TITLE_MAX_CHARS - 1].rstrip() + "…"


async def prepare_turn(
    factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID, conversation_id: uuid.UUID, text: str
) -> Turn:
    """Validate, save the user's message, create the assistant placeholder and build the model's history."""
    async with factory() as session:
        conversation = await conversation_service.get(session, user_id, conversation_id)  # 404 if not the caller's
        if await repo.has_active_stream(session, conversation.id, max_age=STREAM_STALE_AFTER):
            raise StreamInProgressError()
        first_message = not await repo.has_any(session, conversation.id)

        # A thread is ordered by created_at. The question and the reply placeholder are created together, and
        # equal timestamps would be ordered by random UUID (reply before question), so the reply is stamped
        # strictly later. Never rely on the clock having advanced between two statements.
        now = datetime.now(timezone.utc)
        user_message = await repo.add(
            session, conversation_id=conversation.id, role="user", parts=text_parts(text), status="complete",
            created_at=now,
        )
        if first_message and conversation.title == conversation_service.DEFAULT_TITLE:
            conversation.title = title_from(text)  # name the chat after its first question
        conversation.updated_at = datetime.now(timezone.utc)
        assistant = await repo.add(
            session, conversation_id=conversation.id, role="assistant", parts=text_parts(""), status="streaming",
            created_at=now + timedelta(microseconds=1),
        )
        rows = await repo.list_for_conversation(session, user_id, conversation.id)
        # What the model sees: finished or interrupted turns with text (never the empty placeholder or failed ones).
        history = [
            ChatMessage(m.role, m.text)
            for m in rows
            if m.id != assistant.id and m.text and m.status in ("complete", "interrupted")
        ][-settings.llm_max_history_messages :]
        await session.commit()
        return Turn(user_message.id, assistant.id, history)


async def _finalize(
    factory: async_sessionmaker[AsyncSession], message_id: uuid.UUID, text: str, status: str, usage: Usage | None
) -> None:
    async with factory() as session:
        message = await session.get(Message, message_id)
        if message is None:  # the conversation was deleted mid-stream: nothing left to update
            return
        message.parts = text_parts(text)
        message.status = status
        if usage is not None:
            message.tokens_in, message.tokens_out = usage.tokens_in, usage.tokens_out
        conversation = await session.get(Conversation, message.conversation_id)
        if conversation is not None:
            conversation.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def stream_turn(
    factory: async_sessionmaker[AsyncSession], provider: LLMProvider, turn: Turn
) -> AsyncIterator[str]:
    queue: asyncio.Queue = asyncio.Queue()

    async def produce() -> None:
        try:
            async for event in provider.stream(turn.history, system=SYSTEM_PROMPT):
                await queue.put(event)
            await queue.put(_DONE)
        except LLMError as exc:
            await queue.put(exc)
        except asyncio.CancelledError:
            raise
        except Exception:  # a provider bug must never surface as a hung stream
            log.exception("unexpected error from the language model provider")
            await queue.put(LLMError())

    producer = asyncio.create_task(produce())
    text: list[str] = []
    usage: Usage | None = None
    finalized = False
    try:
        yield sse("start", {"user_message_id": str(turn.user_message_id), "assistant_message_id": str(turn.assistant_message_id)})
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield ": ping\n\n"  # keeps proxies from closing an idle connection while the model thinks
                continue
            if item is _DONE:
                await _finalize(factory, turn.assistant_message_id, "".join(text), "complete", usage)
                finalized = True
                yield sse("done", {
                    "message_id": str(turn.assistant_message_id),
                    "tokens_in": usage.tokens_in if usage else None,
                    "tokens_out": usage.tokens_out if usage else None,
                })
                return
            if isinstance(item, LLMError):
                await _finalize(factory, turn.assistant_message_id, "".join(text), "error", usage)
                finalized = True
                yield sse("error", {"code": item.code, "message": item.message, "message_id": str(turn.assistant_message_id)})
                return
            if isinstance(item, TextDelta):
                text.append(item.text)
                yield sse("token", {"text": item.text})
            elif isinstance(item, Usage):
                usage = item
    finally:
        producer.cancel()  # stops the model call (and its upstream connection) if we are leaving early
        if not finalized:
            # The consumer went away (Stop, closed tab, network drop). Save what we have as 'interrupted'.
            # Shielded: during cancellation a plain await would itself be cancelled and the write lost.
            with anyio.CancelScope(shield=True):
                await _finalize(factory, turn.assistant_message_id, "".join(text), "interrupted", usage)
