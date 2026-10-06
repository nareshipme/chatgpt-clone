import uuid
from datetime import datetime, timedelta, timezone

from app.security import create_access_token


async def test_me_requires_authentication(client):
    res = await client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"
    assert res.headers["www-authenticate"] == "Bearer"


async def test_me_rejects_a_garbage_token(client):
    res = await client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401 and res.json()["error"]["code"] == "invalid_token"


async def test_me_rejects_an_expired_token(client, register_user):
    a = await register_user("a@example.com")
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    expired = create_access_token(a["user"]["id"], now=past, expires_delta=timedelta(minutes=1))
    res = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401 and res.json()["error"]["code"] == "invalid_token"


async def test_me_rejects_a_valid_token_for_a_user_that_does_not_exist(client):
    ghost = create_access_token(str(uuid.uuid4()))
    res = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {ghost}"})
    assert res.status_code == 401 and res.json()["error"]["code"] == "invalid_token"


async def test_me_rejects_a_token_whose_subject_is_not_a_uuid(client):
    res = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {create_access_token('not-a-uuid')}"})
    assert res.status_code == 401


async def test_each_user_only_ever_sees_themselves(client, register_user):
    a = await register_user("a@example.com", display_name="Alice")
    b = await register_user("b@example.com", display_name="Bob")
    me_a = (await client.get("/api/v1/me", headers=a["headers"])).json()
    me_b = (await client.get("/api/v1/me", headers=b["headers"])).json()
    assert me_a["email"] == "a@example.com" and me_a["display_name"] == "Alice"
    assert me_b["email"] == "b@example.com" and me_b["display_name"] == "Bob"
    assert me_a["id"] != me_b["id"]
    assert "password" not in str(me_a)
