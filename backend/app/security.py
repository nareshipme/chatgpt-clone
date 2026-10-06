"""Password hashing and access-token helpers. No database or HTTP code lives here."""
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

# Argon2id with the library's default (OWASP-aligned) cost parameters.
_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Return a salted Argon2id hash. The salt and parameters are embedded in the result."""
    return _hasher.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    """True only if `plain` matches the hash. Never raises on a bad password or a malformed hash."""
    try:
        return _hasher.verify(password_hash, plain)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses weaker parameters than the current defaults."""
    return _hasher.check_needs_rehash(password_hash)


# ---------------------------------------------------------------- access tokens
ACCESS_TOKEN_TYPE = "access"


class TokenError(Exception):
    """The token is missing, malformed, expired, tampered with, or of the wrong type."""


def _secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return settings.jwt_secret


def create_access_token(
    subject: str, *, now: datetime | None = None, expires_delta: timedelta | None = None
) -> str:
    """Sign a short-lived access token whose `sub` is the user id."""
    issued = now or datetime.now(timezone.utc)
    lifetime = expires_delta or timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": subject,
        "type": ACCESS_TOKEN_TYPE,
        "iat": issued,
        "exp": issued + lifetime,
    }
    return jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Return the verified claims, or raise TokenError. The algorithm is pinned (never read from the token)."""
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid or expired token") from exc
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise TokenError("wrong token type")
    return claims
