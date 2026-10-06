import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.services import auth_service, conversation_service as svc
from app.services.conversation_service import ConversationNotFoundError, InvalidCursorError


@pytest.fixture
async def session(migrated_db):
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


async def _user(session, email):
    return await auth_service.register(session, email=email, password="a-long-enough-pw", display_name=email)


@pytest.fixture
async def alice(session):
    return await _user(session, "alice@example.com")


@pytest.fixture
async def bob(session):
    return await _user(session, "bob@example.com")


async def _make(session, user, title):
    conversation = await svc.create(session, user.id, title)
    await asyncio.sleep(0.003)  # distinct updated_at values so ordering assertions are deterministic
    return conversation


async def test_create_uses_a_default_title_and_trims_custom_ones(session, alice):
    assert (await svc.create(session, alice.id)).title == "New chat"
    assert (await svc.create(session, alice.id, "   ")).title == "New chat"
    assert (await svc.create(session, alice.id, "  Trip plan  ")).title == "Trip plan"
    assert len((await svc.create(session, alice.id, "x" * 500)).title) == 200


async def test_a_user_cannot_get_update_or_delete_another_users_conversation(session, alice, bob):
    mine = await svc.create(session, alice.id, "Alice private")
    with pytest.raises(ConversationNotFoundError):
        await svc.get(session, bob.id, mine.id)
    with pytest.raises(ConversationNotFoundError):
        await svc.update(session, bob.id, mine.id, title="hijacked")
    with pytest.raises(ConversationNotFoundError):
        await svc.delete(session, bob.id, mine.id)
    assert (await svc.get(session, alice.id, mine.id)).title == "Alice private"  # untouched


async def test_listing_only_returns_the_callers_conversations(session, alice, bob):
    await svc.create(session, alice.id, "A1")
    await svc.create(session, bob.id, "B1")
    assert [c.title for c in (await svc.list_page(session, alice.id)).items] == ["A1"]
    assert [c.title for c in (await svc.list_page(session, bob.id)).items] == ["B1"]


async def test_unknown_id_is_not_found(session, alice):
    with pytest.raises(ConversationNotFoundError):
        await svc.get(session, alice.id, uuid.uuid4())


async def test_most_recently_active_conversation_comes_first(session, alice):
    old = await _make(session, alice, "old")
    await _make(session, alice, "newer")
    await svc.update(session, alice.id, old.id, title="old (renamed)")  # activity bumps updated_at
    titles = [c.title for c in (await svc.list_page(session, alice.id)).items]
    assert titles == ["old (renamed)", "newer"]


async def test_keyset_pagination_has_no_gaps_or_duplicates(session, alice):
    for i in range(5):
        await _make(session, alice, f"c{i}")
    seen, cursor, pages = [], None, 0
    while True:
        page = await svc.list_page(session, alice.id, limit=2, cursor=cursor)
        seen += [c.title for c in page.items]
        pages += 1
        cursor = page.next_cursor
        if cursor is None:
            break
    assert pages == 3
    assert seen == ["c4", "c3", "c2", "c1", "c0"]


async def test_page_size_is_capped(session, alice):
    for i in range(3):
        await svc.create(session, alice.id, f"c{i}")
    assert len((await svc.list_page(session, alice.id, limit=10_000)).items) == 3
    assert len((await svc.list_page(session, alice.id, limit=0)).items) == 1  # at least one row


async def test_invalid_cursor_is_rejected(session, alice):
    with pytest.raises(InvalidCursorError):
        await svc.list_page(session, alice.id, cursor="not-a-cursor")


async def test_search_is_case_insensitive_and_treats_wildcards_literally(session, alice):
    await svc.create(session, alice.id, "Holiday Budget")
    await svc.create(session, alice.id, "Discount is 100% off")
    await svc.create(session, alice.id, "snake_case question")
    await svc.create(session, alice.id, "snakeXcase decoy")
    assert [c.title for c in (await svc.list_page(session, alice.id, q="budget")).items] == ["Holiday Budget"]
    assert [c.title for c in (await svc.list_page(session, alice.id, q="100%")).items] == ["Discount is 100% off"]
    assert [c.title for c in (await svc.list_page(session, alice.id, q="snake_case")).items] == ["snake_case question"]


async def test_archived_conversations_are_hidden_unless_requested(session, alice):
    keep = await svc.create(session, alice.id, "keep")
    gone = await svc.create(session, alice.id, "gone")
    await svc.update(session, alice.id, gone.id, archived=True)
    assert [c.id for c in (await svc.list_page(session, alice.id)).items] == [keep.id]
    assert [c.id for c in (await svc.list_page(session, alice.id, archived=True)).items] == [gone.id]


async def test_delete_removes_the_conversation(session, alice):
    c = await svc.create(session, alice.id, "temp")
    await svc.delete(session, alice.id, c.id)
    with pytest.raises(ConversationNotFoundError):
        await svc.get(session, alice.id, c.id)
