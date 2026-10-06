from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import User
from app.schemas.auth import UserOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
