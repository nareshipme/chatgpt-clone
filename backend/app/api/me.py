from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.domain.personas import effective_persona, get_persona, personas_for
from app.errors import UnprocessableError
from app.models import User
from app.schemas.auth import UserOut

router = APIRouter(tags=["me"])


class PersonaOut(BaseModel):
    id: str
    name: str
    description: str
    starters: list[str]
    selected: bool


class SettingsPatch(BaseModel):
    persona: str


class UnknownPersonaError(UnprocessableError):
    code, default_message = "unknown_persona", "Choose one of the listed personas"


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/personas", response_model=list[PersonaOut])
async def list_personas(user: User = Depends(get_current_user)):
    """The personas that make sense for the caller's company, with the effective one marked."""
    current = effective_persona(user.persona, user.tenant_id)
    return [
        PersonaOut(id=p.id, name=p.name, description=p.description, starters=list(p.starters), selected=bool(current and p.id == current.id))
        for p in personas_for(user.tenant_id)
    ]


@router.patch("/me/settings", response_model=UserOut)
async def update_settings(body: SettingsPatch, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if get_persona(body.persona, user.tenant_id) is None:  # unknown, or another company's persona
        raise UnknownPersonaError()
    user.persona = body.persona
    await db.commit()
    return user
