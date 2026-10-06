import pytest

from app.llm.base import ChatMessage, LLMError, TextDelta, Usage
from app.llm.mock import MockProvider


async def _collect(provider, text):
    return [e async for e in provider.stream([ChatMessage("user", text)])]


async def test_deltas_concatenate_to_a_reply_that_echoes_the_user():
    events = await _collect(MockProvider(), "hello world")
    deltas = [e for e in events if isinstance(e, TextDelta)]
    assert len(deltas) > 3  # streamed in pieces, not one blob
    assert "".join(d.text for d in deltas) == "You said: hello world. This is a demo reply from the mock provider."


async def test_usage_is_emitted_exactly_once_at_the_end():
    events = await _collect(MockProvider(), "count my tokens please")
    assert isinstance(events[-1], Usage)
    assert sum(isinstance(e, Usage) for e in events) == 1
    assert events[-1].tokens_in == 4 and events[-1].tokens_out > 0


async def test_the_reply_is_deterministic():
    a = await _collect(MockProvider(), "same input")
    b = await _collect(MockProvider(), "same input")
    assert a == b


async def test_it_answers_the_last_user_message_in_a_longer_history():
    history = [ChatMessage("user", "first"), ChatMessage("assistant", "ok"), ChatMessage("user", "second question")]
    text = "".join([e.text async for e in MockProvider().stream(history) if isinstance(e, TextDelta)])
    assert "second question" in text and "first" not in text


async def test_the_error_trigger_fails_mid_stream_after_some_text():
    got = []
    with pytest.raises(LLMError) as exc:
        async for event in MockProvider().stream([ChatMessage("user", "please [error] now")]):
            got.append(event)
    assert len(got) == 3  # three words arrived before the failure
    assert exc.value.code == "llm_unavailable"


async def test_the_consumer_can_stop_early_and_close_cleanly():
    stream = MockProvider().stream([ChatMessage("user", "stop me")])
    first = await anext(stream)
    assert isinstance(first, TextDelta)
    await stream.aclose()  # what happens when the user presses Stop; must not raise


async def test_trigger_words_append_structured_parts_after_the_text_and_before_usage():
    from app.llm.base import PartEvent
    from app.schemas.parts import validate_part

    events = await _collect(MockProvider(), "everything [table] [chart] [image] [choices]")
    kinds = [type(e).__name__ for e in events]
    assert kinds[-1] == "Usage" and kinds.count("PartEvent") == 4
    assert kinds.index("PartEvent") > max(i for i, k in enumerate(kinds) if k == "TextDelta")
    parts = [e.part for e in events if isinstance(e, PartEvent)]
    assert [p["type"] for p in parts] == ["table", "chart", "image", "actions"]
    assert all(validate_part(p) is not None for p in parts)  # the demo parts satisfy the real validation


async def test_no_trigger_means_no_parts():
    from app.llm.base import PartEvent

    assert not any(isinstance(e, PartEvent) for e in await _collect(MockProvider(), "plain question"))
