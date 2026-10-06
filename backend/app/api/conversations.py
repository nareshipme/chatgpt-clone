import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.conversation import ConversationCreate, ConversationOut, ConversationPage, ConversationUpdate
from app.services import conversation_service as svc

# Every route depends on get_current_user, and every service call receives user.id: ownership is
# enforced in the query itself, not by remembering to check afterwards.
router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationPage)
async def list_conversations(
    limit: int = Query(svc.DEFAULT_PAGE_SIZE, ge=1, le=svc.MAX_PAGE_SIZE),
    cursor: str | None = Query(None, max_length=200),
    q: str | None = Query(None, max_length=100, description="Case-insensitive title search"),
    archived: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await svc.list_page(db, user.id, limit=limit, cursor=cursor, q=q, archived=archived)
    return ConversationPage(items=[ConversationOut.model_validate(c) for c in page.items], next_cursor=page.next_cursor)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.create(db, user.id, body.title if body else None)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await svc.get(db, user.id, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.update(db, user.id, conversation_id, title=body.title, archived=body.archived)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await svc.delete(db, user.id, conversation_id)
    return Response(status_code=204)
