import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.llm.base import ChatMessage, LLMError, TextDelta, Usage
from app.llm.factory import get_llm_provider
from app.llm.mock import MockProvider
from app.main import app
from app.models import Message
from app.services import chat_service

BASE = "/api/v1/conversations"


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    """Turn an SSE body into [(event, data)], ignoring comment (heartbeat) lines."""
    frames = []
    for block in raw.strip().split("\n\n"):
        event, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event:
            frames.append((event, data))
    return frames


async def _conversation(client, headers, title="New chat"):
    return (await client.post(BASE, json={"title": title}, headers=headers)).json()


async def _send(client, headers, conversation_id, text):
    return await client.post(f"{BASE}/{conversation_id}/messages", json={"content": text}, headers=headers)


async def _thread(client, headers, conversation_id):
    return (await client.get(f"{BASE}/{conversation_id}/messages", headers=headers)).json()["items"]


# ------------------------------------------------------------------ the happy path
async def test_a_reply_streams_start_tokens_then_done_and_is_saved(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    res = await _send(client, a["headers"], c["id"], "hello world")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.headers["x-accel-buffering"] == "no" and res.headers["cache-control"] == "no-cache"

    frames = parse_sse(res.text)
    names = [e for e, _ in frames]
    assert names[0] == "start" and names[-1] == "done" and names.count("done") == 1
    streamed = "".join(d["text"] for e, d in frames if e == "token")
    assert streamed == "You said: hello world. This is a demo reply from the mock provider."
    assert names.count("token") > 3  # delivered in pieces

    thread = await _thread(client, a["headers"], c["id"])
    assert [(m["role"], m["status"]) for m in thread] == [("user", "complete"), ("assistant", "complete")]
    assert thread[0]["parts"] == [{"type": "text", "text": "hello world"}]
    assert thread[1]["parts"] == [{"type": "text", "text": streamed}]  # what was streamed is what was stored
    done = frames[-1][1]
    assert done["message_id"] == thread[1]["id"] and done["tokens_out"] > 0


async def test_the_first_message_names_the_conversation_and_later_ones_do_not(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    await _send(client, a["headers"], c["id"], "Plan a   three day trip to Lisbon")
    title = (await client.get(f"{BASE}/{c['id']}", headers=a["headers"])).json()["title"]
    assert title == "Plan a three day trip to Lisbon"
    await _send(client, a["headers"], c["id"], "second question")
    assert (await client.get(f"{BASE}/{c['id']}", headers=a["headers"])).json()["title"] == title


async def test_a_custom_title_is_never_overwritten(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"], title="My own title")
    await _send(client, a["headers"], c["id"], "anything")
    assert (await client.get(f"{BASE}/{c['id']}", headers=a["headers"])).json()["title"] == "My own title"


async def test_a_long_first_message_gives_a_trimmed_title(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    await _send(client, a["headers"], c["id"], "word " * 100)
    title = (await client.get(f"{BASE}/{c['id']}", headers=a["headers"])).json()["title"]
    assert len(title) <= 60 and title.endswith("…")


async def test_the_model_receives_the_whole_conversation_so_far(client, register_user):
    seen: list[list[ChatMessage]] = []

    class Recorder(MockProvider):
        async def stream(self, messages, **kw):
            seen.append(list(messages))
            async for event in super().stream(messages, **kw):
                yield event

    app.dependency_overrides[get_llm_provider] = lambda: Recorder()
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    await _send(client, a["headers"], c["id"], "first")
    await _send(client, a["headers"], c["id"], "second")
    assert [(m.role, m.content) for m in seen[0]] == [("user", "first")]
    roles = [m.role for m in seen[1]]
    assert roles == ["user", "assistant", "user"] and seen[1][-1].content == "second"
    assert "You said: first" in seen[1][1].content  # the earlier reply is part of the context


# ------------------------------------------------------------------ errors before the stream opens
async def test_authentication_is_required(client):
    assert (await client.post(f"{BASE}/{uuid.uuid4()}/messages", json={"content": "x"})).status_code == 401


async def test_another_users_conversation_is_a_json_404_and_nothing_is_saved(client, register_user):
    a = await register_user("a@example.com")
    b = await register_user("b@example.com")
    c = await _conversation(client, a["headers"], "private")
    res = await _send(client, b["headers"], c["id"], "let me in")
    assert res.status_code == 404 and res.json()["error"]["code"] == "conversation_not_found"
    assert await _thread(client, a["headers"], c["id"]) == []  # no message leaked into Alice's thread


@pytest.mark.parametrize("payload", [{}, {"content": ""}, {"content": "   "}, {"content": "x" * 8001}])
async def test_invalid_content_is_a_422(client, register_user, payload):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    res = await client.post(f"{BASE}/{c['id']}/messages", json=payload, headers=a["headers"])
    assert res.status_code == 422 and res.json()["error"]["code"] == "validation_error"
    assert await _thread(client, a["headers"], c["id"]) == []


# ------------------------------------------------------------------ failure and concurrency
async def test_a_model_failure_mid_stream_keeps_the_partial_text_and_marks_the_message_as_error(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    res = await _send(client, a["headers"], c["id"], "please [error] now")
    frames = parse_sse(res.text)
    assert [e for e, _ in frames][-1] == "error" and "done" not in [e for e, _ in frames]
    assert frames[-1][1]["code"] == "llm_unavailable"
    assert "traceback" not in res.text.lower() and "mock" not in frames[-1][1]["message"].lower()
    thread = await _thread(client, a["headers"], c["id"])
    assert thread[1]["status"] == "error"
    assert thread[1]["parts"][0]["text"].startswith("You said:")  # the three words that arrived are kept


async def test_a_second_message_while_a_reply_is_streaming_is_rejected_with_409(client, register_user, migrated_db):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s:  # simulate a reply that is still streaming
        s.add(Message(conversation_id=uuid.UUID(c["id"]), role="assistant", parts=[], status="streaming"))
        await s.commit()
    await engine.dispose()
    res = await _send(client, a["headers"], c["id"], "too soon")
    assert res.status_code == 409 and res.json()["error"]["code"] == "stream_in_progress"
    assert len(await _thread(client, a["headers"], c["id"])) == 1  # the rejected message was not saved


async def test_an_abandoned_streaming_row_does_not_block_the_conversation_forever(client, register_user, migrated_db):
    from datetime import datetime, timedelta, timezone

    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s:  # a crash left this row 'streaming' an hour ago
        s.add(Message(conversation_id=uuid.UUID(c["id"]), role="assistant", parts=[], status="streaming",
                      created_at=datetime.now(timezone.utc) - timedelta(hours=1)))
        await s.commit()
    await engine.dispose()
    assert (await _send(client, a["headers"], c["id"], "hello again")).status_code == 200


# ------------------------------------------------------------------ stopping (client disconnect)
async def test_stopping_mid_stream_saves_the_partial_reply_as_interrupted(migrated_db):
    """What happens when the user presses Stop or closes the tab: the consumer closes the stream early."""
    from app.services import auth_service, conversation_service

    engine = create_async_engine(migrated_db)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        user = await auth_service.register(s, email="u@example.com", password="a-long-enough-pw", display_name="U")
        conv = await conversation_service.create(s, user.id)
    turn = await chat_service.prepare_turn(factory, user.id, conv.id, "tell me a long story")

    stream = chat_service.stream_turn(factory, MockProvider(delay=0.01), turn)
    await anext(stream)  # start
    await anext(stream)  # first token
    await anext(stream)  # second token
    await stream.aclose()  # the consumer goes away

    async with factory() as s:
        row = await s.get(Message, turn.assistant_message_id)
        assert row.status == "interrupted"
        assert row.text.startswith("You said:") and "demo reply" not in row.text  # partial, not the full reply
    await engine.dispose()


async def test_an_interrupted_reply_is_included_in_the_next_turns_context(migrated_db):
    from app.services import auth_service, conversation_service

    engine = create_async_engine(migrated_db)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        user = await auth_service.register(s, email="u@example.com", password="a-long-enough-pw", display_name="U")
        conv = await conversation_service.create(s, user.id)
    turn = await chat_service.prepare_turn(factory, user.id, conv.id, "first question")
    stream = chat_service.stream_turn(factory, MockProvider(), turn)
    await anext(stream)
    await anext(stream)
    await stream.aclose()
    next_turn = await chat_service.prepare_turn(factory, user.id, conv.id, "follow up")
    assert [m.role for m in next_turn.history] == ["user", "assistant", "user"]
    await engine.dispose()


# ------------------------------------------------------------------ structured parts
async def test_structured_parts_stream_in_order_and_are_saved_in_order(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    res = await _send(client, a["headers"], c["id"], "show me [table] and [chart]")
    frames = parse_sse(res.text)
    names = [e for e, _ in frames]
    assert names[0] == "start" and names[-1] == "done"
    part_frames = [d for e, d in frames if e == "part"]
    assert [p["type"] for p in part_frames] == ["table", "chart"]
    assert names.index("part") > max(i for i, n in enumerate(names) if n == "token")  # text first, then parts

    saved = (await _thread(client, a["headers"], c["id"]))[1]
    assert [p["type"] for p in saved["parts"]] == ["text", "table", "chart"]
    assert saved["parts"][1]["rows"][0][0] == "North"
    assert saved["status"] == "complete"


async def test_image_and_choice_parts_are_saved_with_their_content(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    await _send(client, a["headers"], c["id"], "pictures [image] and [choices]")
    parts = (await _thread(client, a["headers"], c["id"]))[1]["parts"]
    image = next(p for p in parts if p["type"] == "image")
    actions = next(p for p in parts if p["type"] == "actions")
    assert image["url"].startswith("https://") and image["alt"]
    assert [o["id"] for o in actions["options"]] == ["bullets", "short", "detail"]


async def test_a_plain_reply_is_still_a_single_text_part(client, register_user):
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    res = await _send(client, a["headers"], c["id"], "just words")
    assert "part" not in [e for e, _ in parse_sse(res.text)]
    assert [p["type"] for p in (await _thread(client, a["headers"], c["id"]))[1]["parts"]] == ["text"]


async def test_an_invalid_part_is_dropped_and_the_stream_carries_on(client, register_user):
    from app.llm.base import PartEvent

    class Sloppy(MockProvider):
        async def stream(self, messages, **kw):
            yield TextDelta("before ")
            yield PartEvent({"type": "image", "url": "javascript:alert(1)", "alt": "evil"})  # unsafe
            yield PartEvent({"type": "script", "code": "alert(1)"})  # unknown type
            yield PartEvent({"type": "table", "columns": ["a"], "rows": [["x", "y"]]})  # rows do not match columns
            yield TextDelta("after")
            yield Usage(1, 2)

    app.dependency_overrides[get_llm_provider] = lambda: Sloppy()
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    res = await _send(client, a["headers"], c["id"], "hi")
    frames = parse_sse(res.text)
    assert "part" not in [e for e, _ in frames] and [e for e, _ in frames][-1] == "done"
    assert "javascript" not in res.text and "script" not in res.text.replace("javascript", "")
    saved = (await _thread(client, a["headers"], c["id"]))[1]
    assert saved["parts"] == [{"type": "text", "text": "before after"}]  # nothing unsafe was stored


async def test_text_before_and_after_a_part_stays_in_the_right_order(client, register_user):
    from app.llm.base import PartEvent

    class Interleaved(MockProvider):
        async def stream(self, messages, **kw):
            yield TextDelta("Here is the table: ")
            yield PartEvent({"type": "table", "columns": ["a"], "rows": [[1]]})
            yield TextDelta("and that is all.")

    app.dependency_overrides[get_llm_provider] = lambda: Interleaved()
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    await _send(client, a["headers"], c["id"], "hi")
    parts = (await _thread(client, a["headers"], c["id"]))[1]["parts"]
    assert [p["type"] for p in parts] == ["text", "table", "text"]
    assert parts[0]["text"] == "Here is the table: " and parts[2]["text"] == "and that is all."


async def test_stopping_keeps_the_text_and_parts_that_had_already_arrived(migrated_db):
    from app.llm.base import PartEvent
    from app.services import auth_service, conversation_service

    class TableThenSlow(MockProvider):
        async def stream(self, messages, **kw):
            yield TextDelta("Here you go. ")
            yield PartEvent({"type": "table", "columns": ["a"], "rows": [[1]]})
            for _ in range(50):
                import asyncio
                await asyncio.sleep(0.05)
                yield TextDelta("more ")

    engine = create_async_engine(migrated_db)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        user = await auth_service.register(s, email="u@example.com", password="a-long-enough-pw", display_name="U")
        conv = await conversation_service.create(s, user.id)
    turn = await chat_service.prepare_turn(factory, user.id, conv.id, "go")
    stream = chat_service.stream_turn(factory, TableThenSlow(), turn)
    for _ in range(4):  # start, text, part, one more token
        await anext(stream)
    await stream.aclose()
    async with factory() as s:
        row = await s.get(Message, turn.assistant_message_id)
        assert row.status == "interrupted"
        assert [p["type"] for p in row.parts] == ["text", "table", "text"]
    await engine.dispose()


async def test_the_models_context_contains_only_text_not_structured_parts(client, register_user):
    seen = []

    class Recorder(MockProvider):
        async def stream(self, messages, **kw):
            seen.append([(m.role, m.content) for m in messages])
            async for e in super().stream(messages, **kw):
                yield e

    app.dependency_overrides[get_llm_provider] = lambda: Recorder()
    a = await register_user("a@example.com")
    c = await _conversation(client, a["headers"])
    await _send(client, a["headers"], c["id"], "first [table]")
    await _send(client, a["headers"], c["id"], "second")
    history = seen[1]
    assert [r for r, _ in history] == ["user", "assistant", "user"]
    assert all(isinstance(content, str) for _, content in history)
    assert "North" not in history[1][1]  # table cells are not fed back as text
