import asyncio
import re
from collections.abc import AsyncIterator

from app.llm.base import ChatMessage, LLMError, LLMEvent, TextDelta, Usage

_WORD = re.compile(r"\S+\s*")


class MockProvider:
    """Deterministic, offline provider for tests, CI and a no-key demo.

    Replies by echoing the last user message, one word at a time. Trigger words let tests exercise failure
    and slow paths without a network:
      - a message containing "[error]" fails after the first few words (mid-stream failure)
      - a message containing "[slow]" streams slowly, so a test can press Stop part-way
    """

    name = "mock"

    def __init__(self, delay: float = 0.0):
        self.delay = delay

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[LLMEvent]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        reply = f"You said: {last_user.strip()}. This is a demo reply from the mock provider."
        words = _WORD.findall(reply)
        delay = 0.15 if "[slow]" in last_user else self.delay
        for i, word in enumerate(words):
            if "[error]" in last_user and i == 3:
                raise LLMError("llm_unavailable", "The assistant is unavailable right now.")
            if delay:
                await asyncio.sleep(delay)
            yield TextDelta(word)
        prompt_words = sum(len(m.content.split()) for m in messages)
        yield Usage(tokens_in=prompt_words, tokens_out=len(words))
