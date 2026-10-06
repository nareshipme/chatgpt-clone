from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, UnauthorizedError, UnprocessableError
from app.models import Tenant, User
from app.repositories import users
from app.security import hash_password, password_needs_rehash, verify_password


class EmailTakenError(ConflictError):
    code, default_message = "email_taken", "An account with this email already exists"


class UnknownTenantError(UnprocessableError):
    code, default_message = "unknown_tenant", "Choose one of the listed demo companies"


class InvalidCredentialsError(UnauthorizedError):
    code, default_message = "invalid_credentials", "Invalid email or password"


_dummy_hash: str | None = None


def _timing_decoy_hash() -> str:
    """A valid hash to verify against when the email is unknown, so a miss costs the same as a wrong password."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("decoy-password-for-constant-time-login")
    return _dummy_hash


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register(
    session: AsyncSession, *, email: str, password: str, display_name: str, tenant_id: str = "northwind"
) -> User:
    email = normalize_email(email)
    if await session.get(Tenant, tenant_id) is None:
        raise UnknownTenantError()
    if await users.get_by_email(session, email):
        raise EmailTakenError()
    user = await users.add(
        session, email=email, password_hash=hash_password(password), display_name=display_name, tenant_id=tenant_id
    )
    try:
        await session.commit()
    except IntegrityError:
        # Two concurrent registrations passed the check above; the unique constraint caught the loser.
        await session.rollback()
        raise EmailTakenError() from None
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = await users.get_by_email(session, normalize_email(email))
    stored = user.password_hash if user else _timing_decoy_hash()
    password_ok = verify_password(stored, password)
    if user is None or not password_ok:
        # Same error for "no such user" and "wrong password": do not reveal which emails are registered.
        raise InvalidCredentialsError()
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        await session.commit()
    return user
