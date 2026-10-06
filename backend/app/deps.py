import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.errors import UnauthorizedError
from app.models import User
from app.repositories import users
from app.security import TokenError, decode_access_token

# auto_error=False so a missing header goes through our unified error format instead of FastAPI's default.
_bearer = HTTPBearer(auto_error=False)


class InvalidTokenError(UnauthorizedError):
    code, default_message = "invalid_token", "Invalid or expired token"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer access token. Every protected endpoint depends on this."""
    if credentials is None:
        raise UnauthorizedError()
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (TokenError, ValueError):
        raise InvalidTokenError() from None
    user = await users.get_by_id(db, user_id)
    if user is None:  # valid signature but the account no longer exists
        raise InvalidTokenError()
    return user
