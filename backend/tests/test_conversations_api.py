import uuid

import pytest

BASE = "/api/v1/conversations"


async def _create(client, headers, title=None):
    res = await client.post(BASE, json={"title": title} if title is not None else {}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# ------------------------------------------------------------------ authentication
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", BASE),
        ("POST", BASE),
        ("GET", f"{BASE}/{uuid.uuid4()}"),
        ("PATCH", f"{BASE}/{uuid.uuid4()}"),
        ("DELETE", f"{BASE}/{uuid.uuid4()}"),
    ],
)
async def test_every_conversation_route_requires_authentication(client, method, path):
    res = await client.request(method, path, json={"title": "x"} if method in ("POST", "PATCH") else None)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


# ------------------------------------------------------------------ happy path
async def test_create_get_rename_archive_and_delete(client, register_user):
    a = await register_user("a@example.com")
    created = await _create(client, a["headers"], "First chat")
    assert created["title"] == "First chat" and created["archived"] is False

    got = await client.get(f"{BASE}/{created['id']}", headers=a["headers"])
    assert got.status_code == 200 and got.json()["id"] == created["id"]

    renamed = await client.patch(f"{BASE}/{created['id']}", json={"title": "Renamed"}, headers=a["headers"])
    assert renamed.status_code == 200 and renamed.json()["title"] == "Renamed"
    assert renamed.json()["updated_at"] >= created["updated_at"]

    archived = await client.patch(f"{BASE}/{created['id']}", json={"archived": True}, headers=a["headers"])
    assert archived.json()["archived"] is True

    assert (await client.delete(f"{BASE}/{created['id']}", headers=a["headers"])).status_code == 204
    assert (await client.get(f"{BASE}/{created['id']}", headers=a["headers"])).status_code == 404


async def test_create_without_a_body_uses_the_default_title(client, register_user):
    a = await register_user("a@example.com")
    res = await client.post(BASE, headers=a["headers"])
    assert res.status_code == 201 and res.json()["title"] == "New chat"


# ------------------------------------------------------------------ ownership isolation (the important part)
async def test_user_b_cannot_read_change_or_delete_user_a_conversation(client, register_user):
    a = await register_user("a@example.com")
    b = await register_user("b@example.com")
    mine = await _create(client, a["headers"], "Alice secret")
    url = f"{BASE}/{mine['id']}"

    for res in (
        await client.get(url, headers=b["headers"]),
        await client.patch(url, json={"title": "hijacked"}, headers=b["headers"]),
        await client.delete(url, headers=b["headers"]),
    ):
        assert res.status_code == 404  # 404, not 403: do not reveal that the id exists
        assert res.json()["error"]["code"] == "conversation_not_found"

    still = await client.get(url, headers=a["headers"])
    assert still.status_code == 200 and still.json()["title"] == "Alice secret"


async def test_listings_never_include_other_users_conversations(client, register_user):
    a = await register_user("a@example.com")
    b = await register_user("b@example.com")
    await _create(client, a["headers"], "A only")
    await _create(client, b["headers"], "B only")
    a_titles = [c["title"] for c in (await client.get(BASE, headers=a["headers"])).json()["items"]]
    b_titles = [c["title"] for c in (await client.get(BASE, headers=b["headers"])).json()["items"]]
    assert a_titles == ["A only"] and b_titles == ["B only"]
    # searching for the other user's title finds nothing either
    leak = await client.get(BASE, params={"q": "B only"}, headers=a["headers"])
    assert leak.json()["items"] == []


# ------------------------------------------------------------------ pagination, search, archive
async def test_pagination_walks_every_conversation_exactly_once(client, register_user):
    a = await register_user("a@example.com")
    for i in range(5):
        await _create(client, a["headers"], f"c{i}")
    titles, cursor, pages = [], None, 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        body = (await client.get(BASE, params=params, headers=a["headers"])).json()
        titles += [c["title"] for c in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert pages == 3 and sorted(titles) == ["c0", "c1", "c2", "c3", "c4"] and len(set(titles)) == 5


async def test_invalid_cursor_returns_400(client, register_user):
    a = await register_user("a@example.com")
    res = await client.get(BASE, params={"cursor": "garbage"}, headers=a["headers"])
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_cursor"


async def test_search_and_archive_filters(client, register_user):
    a = await register_user("a@example.com")
    await _create(client, a["headers"], "Holiday budget")
    old = await _create(client, a["headers"], "Old project")
    await client.patch(f"{BASE}/{old['id']}", json={"archived": True}, headers=a["headers"])
    found = (await client.get(BASE, params={"q": "BUDGET"}, headers=a["headers"])).json()["items"]
    assert [c["title"] for c in found] == ["Holiday budget"]
    default = (await client.get(BASE, headers=a["headers"])).json()["items"]
    assert [c["title"] for c in default] == ["Holiday budget"]
    archived = (await client.get(BASE, params={"archived": "true"}, headers=a["headers"])).json()["items"]
    assert [c["title"] for c in archived] == ["Old project"]


# ------------------------------------------------------------------ input validation
async def test_validation_errors_use_the_unified_422_shape(client, register_user):
    a = await register_user("a@example.com")
    c = await _create(client, a["headers"], "x")
    cases = [
        await client.patch(f"{BASE}/{c['id']}", json={}, headers=a["headers"]),  # no fields at all
        await client.patch(f"{BASE}/{c['id']}", json={"title": ""}, headers=a["headers"]),  # empty title
        await client.post(BASE, json={"title": "x" * 201}, headers=a["headers"]),  # too long
        await client.get(f"{BASE}/not-a-uuid", headers=a["headers"]),  # malformed id
        await client.get(BASE, params={"limit": 0}, headers=a["headers"]),
        await client.get(BASE, params={"limit": 51}, headers=a["headers"]),
    ]
    for res in cases:
        assert res.status_code == 422, res.text
        assert res.json()["error"]["code"] == "validation_error"
