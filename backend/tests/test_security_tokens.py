import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.security import TokenError, create_access_token, decode_access_token

SECRET = "test-secret-with-enough-length-for-hs256-0123456789"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", SECRET)


def test_round_trip_returns_subject_and_type():
    claims = decode_access_token(create_access_token("user-123"))
    assert claims["sub"] == "user-123"
    assert claims["type"] == "access"


def test_expired_token_is_rejected():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = create_access_token("u", now=past, expires_delta=timedelta(minutes=5))
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_tampered_payload_is_rejected():
    """Rewrite `sub` but keep the original signature: verification must fail."""
    token = create_access_token("user-123")
    head, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["sub"] = "attacker"
    forged_payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    with pytest.raises(TokenError):
        decode_access_token(".".join([head, forged_payload, sig]))


def test_token_signed_with_another_secret_is_rejected():
    forged = jwt.encode(
        {"sub": "u", "type": "access", "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret-0123456789-0123456789", algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(forged)


def test_alg_none_token_is_rejected():
    unsigned = jwt.encode({"sub": "u", "type": "access", "iat": 1, "exp": 4102444800}, key=None, algorithm="none")
    with pytest.raises(TokenError):
        decode_access_token(unsigned)


def test_wrong_token_type_is_rejected():
    now = datetime.now(timezone.utc)
    refresh_like = jwt.encode(
        {"sub": "u", "type": "refresh", "iat": now, "exp": now + timedelta(days=1)}, SECRET, algorithm="HS256"
    )
    with pytest.raises(TokenError):
        decode_access_token(refresh_like)


def test_garbage_input_is_rejected():
    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt")


def test_missing_secret_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", None)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        create_access_token("u")
