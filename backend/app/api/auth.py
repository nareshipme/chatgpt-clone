from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.errors import error_response
from app.repositories import users
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token
from app.services import auth_service, session_service
from app.services.session_service import InvalidRefreshTokenError

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
# Scope the cookie to the auth endpoints so it is not sent with every API request.
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,  # JavaScript cannot read it, so XSS cannot steal it
        secure=settings.cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs: baseline CSRF protection for /refresh and /logout
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.register(
        db, email=body.email, password=body.password, display_name=body.display_name
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate(db, email=body.email, password=body.password)
    raw = await session_service.issue(db, user.id)
    await db.commit()
    _set_refresh_cookie(response, raw)
    return TokenResponse(access_token=create_access_token(str(user.id)), user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    try:
        if not refresh_token:
            raise InvalidRefreshTokenError()
        user_id, new_raw = await session_service.rotate(db, refresh_token)
        user = await users.get_by_id(db, user_id)
        if user is None:
            raise InvalidRefreshTokenError()
    except InvalidRefreshTokenError as exc:
        failure = error_response(request, exc)
        _clear_refresh_cookie(failure)  # a dead cookie should not keep being sent
        return failure
    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=create_access_token(str(user.id)), user=UserOut.model_validate(user))


@router.post("/logout", status_code=204)
async def logout(
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    await session_service.revoke(db, refresh_token)
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response
