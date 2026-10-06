"""Real LLM backend for any OpenAI-compatible Chat Completions API (OpenRouter, Poe, Gemini, Groq...).

There is no fallback to another model or to the mock: if the call fails, or the model returns no text,
the user gets a clear error. Only streams text for now.
"""
import logging
from collections.abc import AsyncIterator

import openai
from openai import AsyncOpenAI

from app.llm.base import ChatMessage, LLMError, LLMEvent, TextDelta, ToolCall, Usage
from app.llm.toolmarkup import ToolMarkupFilter

log = logging.getLogger("app.llm.openai_compat")


def _payload(m: ChatMessage) -> dict:
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    if m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content or None,
            "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}} for c in m.tool_calls],
        }
    return {"role": m.role, "content": m.content}


class OpenAICompatProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_s: float = 60.0,
        max_retries: int = 5,
        client: AsyncOpenAI | None = None,
    ):
        self.model = model
        # `client` lets tests inject a fake; the SDK retries connection errors, 429 and 5xx before streaming starts.
        self._client = client or AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=max_retries
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMEvent]:
        payload = ([{"role": "system", "content": system}] if system else []) + [_payload(m) for m in messages]
        kwargs: dict = {"model": self.model, "messages": payload, "stream": True}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = tools

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except openai.OpenAIError as exc:
            raise self._translate(exc) from None

        produced_text = False
        pending: dict[int, dict] = {}  # tool calls arrive in fragments: name once, arguments in pieces
        # Some models write tool calls as text; catch that so it neither shows up in the chat nor goes unrun.
        markup = ToolMarkupFilter() if tools else None
        try:
            async for chunk in response:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    yield Usage(tokens_in=usage.prompt_tokens or 0, tokens_out=usage.completion_tokens or 0)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                for frag in getattr(delta, "tool_calls", None) or []:
                    slot = pending.setdefault(frag.index, {"id": "", "name": "", "arguments": ""})
                    slot["id"] = frag.id or slot["id"]
                    if frag.function is not None:
                        slot["name"] += frag.function.name or ""
                        slot["arguments"] += frag.function.arguments or ""
                text = delta.content
                if text and markup is not None:
                    text = markup.feed(text)
                if text:
                    produced_text = True
                    yield TextDelta(text)
            if markup is not None:
                tail = markup.flush()
                if tail:
                    produced_text = True
                    yield TextDelta(tail)
            for index in sorted(pending):
                call = pending[index]
                if call["name"]:
                    yield ToolCall(call["id"] or f"call-{index}", call["name"], call["arguments"])
            text_calls = markup.calls if markup is not None else []
            for call in text_calls:
                yield call
            if not produced_text and not text_calls and not any(c["name"] for c in pending.values()):
                # Some models (e.g. reasoning ones) return only hidden reasoning. A blank reply is a failure.
                log.warning("empty completion model=%s", self.model)
                raise LLMError("llm_empty", "The assistant returned an empty answer. Please try again.")
        except openai.OpenAIError as exc:
            raise self._translate(exc) from None
        finally:
            # Runs on normal end, on error, and when the consumer stops early (user pressed Stop).
            close = getattr(response, "close", None)
            if close is not None:
                await close()

    @staticmethod
    def _translate(exc: Exception) -> LLMError:
        """Map SDK errors to our small, safe vocabulary. Details go to the server log, never to the client."""
        status = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        log.warning("llm error type=%s status=%s request_id=%s", type(exc).__name__, status, request_id)
        if isinstance(exc, openai.RateLimitError):
            return LLMError("llm_rate_limited", "The assistant is busy right now. Please try again in a moment.")
        if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
            return LLMError("llm_unavailable", "The assistant is taking too long to respond. Please try again.")
        return LLMError("llm_unavailable", "The assistant is unavailable right now.")
