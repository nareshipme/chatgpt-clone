import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_db, get_sessionmaker
from app.deps import get_current_user
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.models import User
from app.schemas.message import MessageList, MessageOut, SendMessageRequest
from app.services import chat_service, message_service

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["messages"])


@router.get("", response_model=MessageList)
async def list_messages(
    conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """The whole thread, oldest first. 404 if the conversation is not the caller's."""
    items = await message_service.list_messages(db, user.id, conversation_id)
    return MessageList(items=[MessageOut.model_validate(m) for m in items])


@router.post("")
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    factory: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
    provider: LLMProvider = Depends(get_llm_provider),
):
    """Send a user message and stream the assistant's reply as Server-Sent Events.

    Events: start, token (repeated), then exactly one of done or error. Failures before the stream opens
    (401, 404, 409, 422) are ordinary JSON errors.
    """
    turn = await chat_service.prepare_turn(factory, user.id, conversation_id, body.content)
    return StreamingResponse(
        chat_service.stream_turn(factory, provider, turn),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # no buffering by Nginx or proxies
    )
