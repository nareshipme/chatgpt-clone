"""Poe backend, via Poe's OpenAI-compatible Chat Completions API.

Docs: https://creator.poe.com/docs/external-applications/openai-compatible-api
Poe model ids are lowercase bot names (e.g. claude-sonnet-5.5). Poe has no JSON-schema structured outputs
and ignores strict tool schemas, so this provider only streams text for now.
"""
import logging
from collections.abc import AsyncIterator

import openai
from openai import AsyncOpenAI

from app.llm.base import ChatMessage, LLMError, LLMEvent, TextDelta, Usage

log = logging.getLogger("app.llm.poe")


class PoeProvider:
    name = "poe"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.poe.com/v1",
        model: str,
        timeout_s: float = 60.0,
        max_retries: int = 2,
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
    ) -> AsyncIterator[LLMEvent]:
        payload = ([{"role": "system", "content": system}] if system else []) + [
            {"role": m.role, "content": m.content} for m in messages
        ]
        kwargs: dict = {"model": self.model, "messages": payload, "stream": True}
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except openai.OpenAIError as exc:
            raise self._translate(exc) from None

        try:
            async for chunk in response:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    yield Usage(tokens_in=usage.prompt_tokens or 0, tokens_out=usage.completion_tokens or 0)
                if not chunk.choices:
                    continue
                text = chunk.choices[0].delta.content
                if text:
                    yield TextDelta(text)
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
        log.warning("poe error type=%s status=%s request_id=%s", type(exc).__name__, status, request_id)
        if isinstance(exc, openai.RateLimitError):
            return LLMError("llm_rate_limited", "The assistant is busy right now. Please try again in a moment.")
        if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
            return LLMError("llm_unavailable", "The assistant is taking too long to respond. Please try again.")
        return LLMError("llm_unavailable", "The assistant is unavailable right now.")
