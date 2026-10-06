PW = "a-long-enough-pw"
COOKIE = "refresh_token"
PATH = "/api/v1/auth"


async def _login(client, email="ada@example.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": PW, "display_name": "Ada"})
    return await client.post("/api/v1/auth/login", json={"email": email, "password": PW})


def _cookie(client):
    return client.cookies.get(COOKIE, path=PATH)


async def test_login_sets_an_httponly_scoped_refresh_cookie(client):
    res = await _login(client)
    header = res.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in header and "httponly" in header and "samesite=lax" in header and f"path={PATH}" in header
    assert "refresh_token" not in res.text  # the token is never in the JSON body


async def test_refresh_rotates_the_cookie_and_returns_a_new_access_token(client):
    login = await _login(client)
    before = _cookie(client)
    res = await client.post("/api/v1/auth/refresh")
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "ada@example.com" and res.json()["access_token"]
    assert _cookie(client) and _cookie(client) != before
    assert login.json()["user"]["id"] == res.json()["user"]["id"]


async def test_refresh_without_a_cookie_is_401(client):
    res = await client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_refresh_token"


def _send_only(client, value):
    """Make the cookie jar hold exactly one refresh cookie (a second one would be sent alongside it)."""
    client.cookies.clear()
    client.cookies.set(COOKIE, value, domain="test", path=PATH)


async def test_replaying_an_old_refresh_cookie_kills_the_whole_session(client):
    await _login(client)
    stolen = _cookie(client)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200  # legitimate rotation
    newest = _cookie(client)
    _send_only(client, stolen)  # the attacker replays the already-used token
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    _send_only(client, newest)  # so the victim's current token is revoked as well
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_revokes_the_session_and_clears_the_cookie(client):
    await _login(client)
    old = _cookie(client)
    res = await client.post("/api/v1/auth/logout")
    assert res.status_code == 204
    assert _cookie(client) is None
    _send_only(client, old)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_without_a_session_is_still_204(client):
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
