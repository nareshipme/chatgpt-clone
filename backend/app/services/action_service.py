"""Proposed actions: the copilot proposes, a human decides, and every step leaves an audit event.

Rules worth being able to explain:
- A button in the chat carries only the action's id. What would happen (type and payload) is stored server-side
  when the copilot proposes it, so a client can never approve something it invented.
- Tenant first, then role: another company's action is a 404 (same as a missing one) before any role check.
- Approving is idempotent and race-safe: one atomic UPDATE ... WHERE status = 'proposed' decides the winner, so a
  double click, a retry or two tabs produce exactly one approval and exactly one audit event.
- The effect is simulated (no real warehouse system exists in this demo) but fully recorded.
- Proposals expire; an expired proposal can no longer be approved.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.tools import ToolError, run_tool
from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import AuditEvent, ProposedAction, User

DECIDER_ROLES = {"planner", "manager"}  # viewers can read but not approve


class ActionNotFoundError(NotFoundError):
    code, default_message = "action_not_found", "Action not found"


class ActionNotPendingError(ConflictError):
    code, default_message = "action_not_pending", "This action has already been decided or has expired."


class ActionInvalidError(ConflictError):
    code, default_message = "action_no_longer_valid", "This action can no longer be carried out."


class RoleNotAllowedError(ForbiddenError):
    code, default_message = "role_not_allowed", "Your role is not allowed to do this."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite returns naive timestamps


def add_audit(session: AsyncSession, *, tenant_id: str, actor_id: uuid.UUID | None, action: str, payload: dict) -> None:
    session.add(AuditEvent(tenant_id=tenant_id, actor_id=actor_id, action=action, payload=payload, created_at=_utcnow()))


async def create_proposal(
    session: AsyncSession, *, tenant_id: str, user_id: uuid.UUID, message_id: uuid.UUID, proposed: dict
) -> ProposedAction:
    now = _utcnow()
    action = ProposedAction(
        tenant_id=tenant_id, message_id=message_id, proposed_by=user_id, type=proposed["type"],
        summary=proposed["summary"][:300], payload=proposed["payload"], created_at=now,
        expires_at=now + timedelta(minutes=settings.action_expiry_minutes),
    )
    session.add(action)
    await session.flush()
    add_audit(session, tenant_id=tenant_id, actor_id=user_id, action="action.proposed",
              payload={"action_id": str(action.id), "type": action.type, "summary": action.summary})
    return action


async def get_visible(session: AsyncSession, user: User, action_id: uuid.UUID) -> ProposedAction:
    """The action if it belongs to the caller's company; 404 otherwise. Lazily marks an overdue proposal expired."""
    action = await session.get(ProposedAction, action_id)
    if action is None or action.tenant_id != user.tenant_id:
        raise ActionNotFoundError()
    if action.status == "proposed" and _aware(action.expires_at) <= _utcnow():
        claimed = await session.execute(
            update(ProposedAction).where(ProposedAction.id == action.id, ProposedAction.status == "proposed").values(status="expired")
        )
        if claimed.rowcount == 1:
            add_audit(session, tenant_id=action.tenant_id, actor_id=None, action="action.expired",
                      payload={"action_id": str(action.id), "summary": action.summary})
        await session.commit()
        await session.refresh(action)
    return action


async def decide(session: AsyncSession, user: User, action_id: uuid.UUID, decision: str) -> ProposedAction:
    """decision is 'approved' or 'dismissed'. Repeating the same decision returns the same result."""
    action = await get_visible(session, user, action_id)
    if user.role not in DECIDER_ROLES:
        raise RoleNotAllowedError("Viewers can look at proposals but not approve or dismiss them.")
    if action.status != "proposed":
        if action.status == decision:
            return action  # idempotent: the same decision twice is not an error and writes nothing new
        raise ActionNotPendingError(f"This action is already {action.status}.")

    result = None
    if decision == "approved":
        try:  # re-check against the data as it is now, not as it was when proposed
            checked = run_tool(user.tenant_id, "propose_rebalance", action.payload)
        except ToolError as exc:
            raise ActionInvalidError(exc.message) from None
        result = {**checked.data, "simulated": True, "note": "Simulated: no real warehouse system was changed in this demo."}

    claimed = await session.execute(
        update(ProposedAction)
        .where(ProposedAction.id == action.id, ProposedAction.status == "proposed")
        .values(status=decision, decided_by=user.id, decided_at=_utcnow(), result=result)
    )
    if claimed.rowcount != 1:  # someone else decided in the meantime
        # no rollback: nothing was written, and rollback would expire the caller's user object too
        await session.refresh(action)
        if action.status == decision:
            return action
        raise ActionNotPendingError(f"This action is already {action.status}.")
    add_audit(
        session, tenant_id=user.tenant_id, actor_id=user.id, action=f"action.{decision}",
        payload={"action_id": str(action.id), "type": action.type, "summary": action.summary, "payload": action.payload, "result": result},
    )
    await session.commit()
    await session.refresh(action)
    return action


async def list_audit(session: AsyncSession, user: User, limit: int = 50) -> list[tuple[AuditEvent, str | None]]:
    if user.role not in DECIDER_ROLES:
        raise RoleNotAllowedError("Viewers cannot read the audit log.")
    rows = await session.execute(
        select(AuditEvent, User.display_name)
        .outerjoin(User, User.id == AuditEvent.actor_id)
        .where(AuditEvent.tenant_id == user.tenant_id)  # the tenant is part of the query, as everywhere else
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return [(event, name) for event, name in rows.all()]
