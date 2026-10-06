"""Password hashing and access-token helpers. No database or HTTP code lives here."""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

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
