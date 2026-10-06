from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Tenant

router = APIRouter(tags=["tenants"])


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    industry: str


@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(db: AsyncSession = Depends(get_db)):
    """Public on purpose: the sign-up form needs it. Demo only; a real product assigns tenants by invitation or SSO."""
    return list(await db.scalars(select(Tenant).order_by(Tenant.name)))
