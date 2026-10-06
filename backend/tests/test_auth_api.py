from app.security import decode_access_token

PW = "a-long-enough-pw"


async def _register(client, email="ada@example.com", password=PW, name="Ada"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password, "display_name": name})


async def test_register_returns_201_and_never_exposes_the_password(client):
    res = await _register(client)
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "ada@example.com" and body["display_name"] == "Ada" and body["id"]
    assert "password" not in res.text and "argon2" not in res.text


async def test_duplicate_email_returns_409_with_email_taken(client):
    await _register(client, email="ada@example.com")
    res = await _register(client, email="ADA@example.com")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


async def test_short_password_returns_422_on_the_password_field(client):
    res = await _register(client, password="short")
    assert res.status_code == 422
    fields = [d["field"] for d in res.json()["error"]["details"]]
    assert "password" in fields


async def test_invalid_email_returns_422(client):
    res = await _register(client, email="not-an-email")
    assert res.status_code == 422
    assert any(d["field"] == "email" for d in res.json()["error"]["details"])


async def test_login_returns_a_token_for_the_right_user(client):
    created = (await _register(client)).json()
    res = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": PW})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"])["sub"] == created["id"]
    assert body["user"]["email"] == "ada@example.com"


async def test_wrong_password_and_unknown_email_return_the_same_401(client):
    await _register(client)
    wrong = await client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "wrong-password-1"})
    unknown = await client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "wrong-password-1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
