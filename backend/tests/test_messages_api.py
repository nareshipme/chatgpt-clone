import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.services import message_service

BASE = "/api/v1/conversations"


async def _conversation(client, headers, title="t"):
    return (await client.post(BASE, json={"title": title}, headers=headers)).json()


async def _seed(migrated_db, conversation_id, user_id, rows):
    """Insert messages directly through the service (the POST endpoint comes in a later checkpoint)."""
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        for role, text in rows:
            await message_service.add_message(s, uuid.UUID(user_id), uuid.UUID(conversation_id), role=role, text=text)
            await asyncio.sleep(0.02)  # a coarse clock (Windows) can give equal timestamps; the tiebreak is a random UUID
        await s.commit()
    await engine.dispose()


async def test_listing_requires_authentication(client):
    res = await client.get(f"{BASE}/{uuid.uuid4()}/messages")
    assert res.status_code == 401


async def test_a_new_conversation_has_no_messages(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    res = await client.get(f"{BASE}/{c['id']}/messages", headers=a["headers"])
    assert res.status_code == 200 and res.json() == {"items": []}


async def test_messages_are_returned_oldest_first_with_typed_parts(client, register_user, migrated_db):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    await _seed(migrated_db, c["id"], a["user"]["id"], [("user", "hi"), ("assistant", "hello there")])
    items = (await client.get(f"{BASE}/{c['id']}/messages", headers=a["headers"])).json()["items"]
    assert [m["role"] for m in items] == ["user", "assistant"]
    assert items[1]["parts"] == [{"type": "text", "text": "hello there"}]
    assert items[0]["status"] == "complete" and items[0]["conversation_id"] == c["id"]


async def test_another_user_gets_404_and_never_sees_the_messages(client, register_user, migrated_db):
    a = await register_user("a@example.com")
    b = await register_user("b@example.com")
    c = await _conversation(client, a["headers"], "private")
    await _seed(migrated_db, c["id"], a["user"]["id"], [("user", "very secret text")])
    res = await client.get(f"{BASE}/{c['id']}/messages", headers=b["headers"])
    assert res.status_code == 404 and res.json()["error"]["code"] == "conversation_not_found"
    assert "very secret text" not in res.text


async def test_unknown_or_malformed_conversation_ids(client, register_user):
    a = await register_user("a@example.com")
    assert (await client.get(f"{BASE}/{uuid.uuid4()}/messages", headers=a["headers"])).status_code == 404
    assert (await client.get(f"{BASE}/not-a-uuid/messages", headers=a["headers"])).status_code == 422
