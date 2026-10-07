import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models import ProposedAction, User
from app.services import action_service

router = APIRouter(tags=["actions"])


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    summary: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None
    result: dict[str, Any] | None = None
    can_decide: bool = False  # lets the UI hide buttons the server would refuse anyway


class AuditOut(BaseModel):
    id: uuid.UUID
    action: str
    actor_name: str | None
    payload: dict[str, Any]
    created_at: datetime


class AuditList(BaseModel):
    items: list[AuditOut]


def _out(action: ProposedAction, user: User) -> ActionOut:
    out = ActionOut.model_validate(action)
    out.can_decide = user.role in action_service.DECIDER_ROLES and action.status == "proposed"
    return out


@router.get("/actions/{action_id}", response_model=ActionOut)
async def get_action(action_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return _out(await action_service.get_visible(db, user, action_id), user)


@router.post("/actions/{action_id}/execute", response_model=ActionOut)
async def execute_action(action_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Approve a proposed action. Safe to call twice: the second call returns the same result and audits nothing new."""
    return _out(await action_service.decide(db, user, action_id, "approved"), user)


@router.post("/actions/{action_id}/dismiss", response_model=ActionOut)
async def dismiss_action(action_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return _out(await action_service.decide(db, user, action_id, "dismissed"), user)


@router.get("/audit", response_model=AuditList)
async def audit_log(limit: int = Query(default=50, ge=1, le=200), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The caller's company's audit trail, newest first. Read-only: nothing in the API can change or delete it."""
    rows = await action_service.list_audit(db, user, limit)
    return AuditList(items=[AuditOut(id=e.id, action=e.action, actor_name=name, payload=e.payload, created_at=e.created_at) for e, name in rows])
