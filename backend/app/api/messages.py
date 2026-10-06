import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.message import MessageList, MessageOut
from app.services import message_service

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["messages"])


@router.get("", response_model=MessageList)
async def list_messages(
    conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """The whole thread, oldest first. 404 if the conversation is not the caller's."""
    items = await message_service.list_messages(db, user.id, conversation_id)
    return MessageList(items=[MessageOut.model_validate(m) for m in items])
