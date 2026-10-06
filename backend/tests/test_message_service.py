import asyncio

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import Message
from app.services import auth_service, conversation_service as convs, message_service as msgs
from app.services.conversation_service import ConversationNotFoundError


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
async def alice_id(alice):
    return alice.id


@pytest.fixture
async def bob(session):
    return await _user(session, "bob@example.com")


async def test_messages_come_back_in_the_order_they_were_added(session, alice):
    c = await convs.create(session, alice.id, "t")
    for role, text in [("user", "hi"), ("assistant", "hello"), ("user", "how are you")]:
        await msgs.add_message(session, alice.id, c.id, role=role, text=text)
        await asyncio.sleep(0.003)
    await session.commit()
    thread = await msgs.list_messages(session, alice.id, c.id)
    assert [(m.role, m.text) for m in thread] == [("user", "hi"), ("assistant", "hello"), ("user", "how are you")]


async def test_message_text_is_built_from_text_parts(session, alice):
    c = await convs.create(session, alice.id)
    m = await msgs.add_message(session, alice.id, c.id, role="user", text="hello")
    assert m.parts == [{"type": "text", "text": "hello"}] and m.text == "hello" and m.status == "complete"


async def test_adding_a_message_bumps_the_conversation_to_the_top(session, alice):
    older = await convs.create(session, alice.id, "older")
    await asyncio.sleep(0.003)
    newer = await convs.create(session, alice.id, "newer")
    await asyncio.sleep(0.003)
    await msgs.add_message(session, alice.id, older.id, role="user", text="activity")
    await session.commit()
    titles = [c.title for c in (await convs.list_page(session, alice.id)).items]
    assert titles == ["older", "newer"]
    assert newer.id != older.id


async def test_a_user_cannot_read_or_write_another_users_thread(session, alice, bob):
    c = await convs.create(session, alice.id, "private")
    await msgs.add_message(session, alice.id, c.id, role="user", text="secret")
    await session.commit()
    with pytest.raises(ConversationNotFoundError):
        await msgs.list_messages(session, bob.id, c.id)
    with pytest.raises(ConversationNotFoundError):
        await msgs.add_message(session, bob.id, c.id, role="user", text="intrusion")
    assert [m.text for m in await msgs.list_messages(session, alice.id, c.id)] == ["secret"]


async def test_repository_level_listing_is_also_scoped_to_the_owner(session, alice, bob):
    from app.repositories import messages as repo

    c = await convs.create(session, alice.id, "private")
    await msgs.add_message(session, alice.id, c.id, role="user", text="secret")
    await session.commit()
    assert await repo.list_for_conversation(session, bob.id, c.id) == []  # no rows, not an error


async def test_database_rejects_unknown_roles_and_statuses(session, alice):
    cid = (await convs.create(session, alice.id)).id  # read the id now: after a rollback attributes are expired
    session.add(Message(conversation_id=cid, role="wizard", parts=[]))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
    session.add(Message(conversation_id=cid, role="user", parts=[], status="bogus"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_deleting_a_conversation_deletes_its_messages(migrated_db, alice_id):
    """Cascade is enforced by the database. SQLite only enforces foreign keys when asked, on every connection."""
    from sqlalchemy import event, select

    engine = create_async_engine(migrated_db)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    async with AsyncSession(engine, expire_on_commit=False) as s:
        c = await convs.create(s, alice_id)
        await msgs.add_message(s, alice_id, c.id, role="user", text="bye")
        await s.commit()
        await convs.delete(s, alice_id, c.id)
        assert (await s.scalars(select(Message))).all() == []
    await engine.dispose()
