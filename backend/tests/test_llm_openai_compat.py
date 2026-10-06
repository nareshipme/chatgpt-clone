from types import SimpleNamespace

import httpx
import openai
import pytest

from app.config import settings
from app.llm.base import ChatMessage, LLMError, TextDelta, ToolCall, Usage
from app.llm.factory import build_provider, validate_llm_config
from app.llm.mock import MockProvider
from app.llm.openai_compat import OpenAICompatProvider

REQ = httpx.Request("POST", "https://api.poe.com/v1/chat/completions")


def chunk(text=None, usage=None, choices=True):
    delta = SimpleNamespace(content=text)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)] if choices else [], usage=usage)


class FakeStream:
    """Stands in for the SDK's async stream: yields chunks, optionally fails part-way, records close()."""

    def __init__(self, chunks, fail_with=None):
        self.chunks, self.fail_with, self.closed = chunks, fail_with, False

    def __aiter__(self):
        async def gen():
            for c in self.chunks:
                yield c
            if self.fail_with:
                raise self.fail_with

        return gen()

    async def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, stream=None, create_error=None):
        self.calls, self._stream, self._error = [], stream, create_error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._stream


def provider(client):
    return OpenAICompatProvider(api_key="secret-key-123", base_url="https://example.test/v1", model="test-model", client=client)


async def collect(p, messages=None, **kw):
    return [e async for e in p.stream(messages or [ChatMessage("user", "hi")], **kw)]


async def test_text_deltas_are_forwarded_and_empty_chunks_ignored():
    stream = FakeStream([chunk("Hel"), chunk(None), chunk(""), chunk(choices=False), chunk("lo")])
    events = await collect(provider(FakeClient(stream)))
    assert events == [TextDelta("Hel"), TextDelta("lo")]


async def test_request_has_model_stream_flag_system_prompt_first_and_optional_temperature():
    client = FakeClient(FakeStream([chunk("x")]))
    await collect(provider(client), [ChatMessage("user", "q")], system="Be brief.")
    call = client.calls[0]
    assert call["model"] == "test-model" and call["stream"] is True
    assert call["messages"] == [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "q"}]
    assert "temperature" not in call  # only sent when asked for

    client2 = FakeClient(FakeStream([chunk("x")]))
    await collect(provider(client2), temperature=0.2)
    assert client2.calls[0]["temperature"] == 0.2


async def test_usage_is_forwarded_when_the_backend_reports_it():
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7)
    events = await collect(provider(FakeClient(FakeStream([chunk("a"), chunk(None, usage=usage, choices=False)]))))
    assert events == [TextDelta("a"), Usage(tokens_in=11, tokens_out=7)]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (openai.RateLimitError("rate limited", response=httpx.Response(429, request=REQ), body=None), "llm_rate_limited"),
        (openai.APIConnectionError(request=REQ), "llm_unavailable"),
        (openai.APITimeoutError(request=REQ), "llm_unavailable"),
        (openai.InternalServerError("boom", response=httpx.Response(500, request=REQ), body=None), "llm_unavailable"),
        (openai.AuthenticationError("bad key secret-key-123", response=httpx.Response(401, request=REQ), body=None), "llm_unavailable"),
    ],
)
async def test_sdk_errors_become_safe_llm_errors_and_never_leak_details(error, code):
    with pytest.raises(LLMError) as exc:
        await collect(provider(FakeClient(create_error=error)))
    assert exc.value.code == code
    assert "secret-key-123" not in exc.value.message and "api.poe.com" not in exc.value.message


async def test_a_failure_mid_stream_delivers_the_text_so_far_then_raises():
    stream = FakeStream([chunk("partial "), chunk("answer")], fail_with=openai.APIConnectionError(request=REQ))
    got = []
    with pytest.raises(LLMError):
        async for e in provider(FakeClient(stream)).stream([ChatMessage("user", "hi")]):
            got.append(e)
    assert got == [TextDelta("partial "), TextDelta("answer")]
    assert stream.closed is True


async def test_the_upstream_stream_is_closed_after_normal_completion():
    stream = FakeStream([chunk("done")])
    await collect(provider(FakeClient(stream)))
    assert stream.closed is True


async def test_stopping_early_closes_the_upstream_stream():
    stream = FakeStream([chunk("a"), chunk("b"), chunk("c")])
    it = provider(FakeClient(stream)).stream([ChatMessage("user", "hi")])
    assert await anext(it) == TextDelta("a")
    await it.aclose()  # user pressed Stop
    assert stream.closed is True


async def test_a_reply_with_no_text_is_an_error_not_a_blank_bubble():
    stream = FakeStream([chunk(None), chunk(None, usage=SimpleNamespace(prompt_tokens=3, completion_tokens=0))])
    with pytest.raises(LLMError) as exc:
        await collect(provider(FakeClient(stream)))
    assert exc.value.code == "llm_empty"


def frag(index, id=None, name=None, args=None):
    fn = SimpleNamespace(name=name, arguments=args)
    delta = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(index=index, id=id, function=fn)])
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)


async def test_streamed_tool_call_fragments_are_reassembled_into_whole_calls():
    stream = FakeStream([
        frag(0, "call_a", "get_lane_cost_carbon", ""), frag(0, None, None, '{"lane": '), frag(0, None, None, '"Atlanta-Miami"}'),
        frag(1, "call_b", "list_at_risk_shipments", "{}"),
    ])
    events = await collect(provider(FakeClient(stream)), tools=[{"type": "function", "function": {"name": "x"}}])
    assert events == [
        ToolCall("call_a", "get_lane_cost_carbon", '{"lane": "Atlanta-Miami"}'),
        ToolCall("call_b", "list_at_risk_shipments", "{}"),
    ]  # a tool-only reply is not "empty"


async def test_a_tool_call_written_as_text_is_hidden_and_turned_into_a_real_call():
    stream = FakeStream([chunk("I will check. <tool_"), chunk("call>get_lane_cost_carbon<arg_key>lane</arg_key><arg_value>Atlanta-Miami</arg_value></tool_call>")])
    events = await collect(provider(FakeClient(stream)), tools=[{"type": "function", "function": {"name": "x"}}])
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["I will check. "]
    assert events[-1] == ToolCall("call-text-1", "get_lane_cost_carbon", '{"lane": "Atlanta-Miami"}')


async def test_without_tools_offered_nothing_is_rewritten():
    stream = FakeStream([chunk("literal <tool_call>x</tool_call> text")])
    events = await collect(provider(FakeClient(stream)))
    assert "".join(e.text for e in events if isinstance(e, TextDelta)) == "literal <tool_call>x</tool_call> text"


async def test_tools_are_sent_only_when_offered_and_tool_messages_use_the_openai_format():
    client = FakeClient(FakeStream([chunk("ok")]))
    history = [
        ChatMessage("user", "q"),
        ChatMessage("assistant", "", tool_calls=(ToolCall("c1", "t", '{"a": 1}'),)),
        ChatMessage("tool", '{"x": 2}', tool_call_id="c1"),
    ]
    await collect(provider(client), history, tools=[{"type": "function", "function": {"name": "t"}}])
    sent = client.calls[0]
    assert sent["tools"][0]["function"]["name"] == "t"
    assert sent["messages"][1] == {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "t", "arguments": '{"a": 1}'}}]}
    assert sent["messages"][2] == {"role": "tool", "tool_call_id": "c1", "content": '{"x": 2}'}
    client2 = FakeClient(FakeStream([chunk("ok")]))
    await collect(provider(client2), history[:1])
    assert "tools" not in client2.calls[0]


# ------------------------------------------------------------------ factory
def configure(monkeypatch, provider="openai_compatible", key="k", secure=False):
    monkeypatch.setattr(settings, "llm_provider", provider)
    monkeypatch.setattr(settings, "llm_api_key", key)
    monkeypatch.setattr(settings, "cookie_secure", secure)


def test_factory_builds_the_real_provider_from_llm_settings(monkeypatch):
    configure(monkeypatch)
    p = build_provider()
    assert isinstance(p, OpenAICompatProvider) and p.model == settings.llm_model
    assert p._client.max_retries == settings.llm_max_retries >= 3  # patient with free-tier 429s


def test_a_missing_key_fails_loudly_instead_of_falling_back_to_the_mock(monkeypatch):
    configure(monkeypatch, key=None)
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        build_provider()
    with pytest.raises(RuntimeError):
        validate_llm_config()


def test_unknown_provider_is_rejected(monkeypatch):
    configure(monkeypatch, provider="poe")
    with pytest.raises(RuntimeError, match="Unknown LLM_PROVIDER"):
        validate_llm_config()


def test_mock_is_for_development_only_and_refused_in_production(monkeypatch):
    configure(monkeypatch, provider="mock", key=None, secure=False)
    assert isinstance(build_provider(), MockProvider)
    configure(monkeypatch, provider="mock", key=None, secure=True)
    with pytest.raises(RuntimeError, match="not allowed in production"):
        validate_llm_config()


# ------------------------------------------------------------------ opt-in: real provider
@pytest.mark.live
async def test_live_provider_streams_a_real_answer():
    import os

    key = os.environ.get("LLM_API_KEY")
    if not key:
        pytest.skip("LLM_API_KEY not set")
    p = OpenAICompatProvider(
        api_key=key,
        base_url=os.environ.get("LLM_BASE_URL", settings.llm_base_url),
        model=os.environ.get("LLM_MODEL", settings.llm_model),
        timeout_s=60,
    )
    events = await collect(p, [ChatMessage("user", "Reply with exactly the word: pong")], temperature=0)
    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert "pong" in text.lower()
