import asyncio
import re
from collections.abc import AsyncIterator

from app.llm.base import ChatMessage, LLMError, LLMEvent, PartEvent, TextDelta, Usage

_WORD = re.compile(r"\S+\s*")

DEMO_PARTS: dict[str, dict] = {
    "[table]": {
        "type": "table",
        "title": "Quarterly sales (demo data)",
        "columns": ["Region", "Q1", "Q2", "Q3"],
        "rows": [["North", 120, 135, 150], ["South", 98, 101, 110], ["West", 143, 128, 160]],
    },
    "[chart]": {
        "type": "chart",
        "kind": "bar",
        "title": "Monthly revenue (demo data)",
        "x": "month",
        "series": [{"key": "revenue", "label": "Revenue"}, {"key": "cost", "label": "Cost"}],
        "data": [
            {"month": "Jan", "revenue": 120, "cost": 80},
            {"month": "Feb", "revenue": 150, "cost": 95},
            {"month": "Mar", "revenue": 170, "cost": 100},
            {"month": "Apr", "revenue": 160, "cost": 110},
        ],
    },
    "[image]": {"type": "image", "url": "https://placehold.co/640x240/3a5876/ffffff/png?text=Demo+image", "alt": "A demo placeholder image"},
    "[choices]": {
        "type": "actions",
        "prompt": "How would you like the answer?",
        "options": [
            {"id": "bullets", "label": "Bullet points", "value": "Please answer in bullet points."},
            {"id": "short", "label": "One short paragraph", "value": "Please answer in one short paragraph."},
            {"id": "detail", "label": "More detail", "value": "Please explain in more detail."},
        ],
    },
}


class MockProvider:
    """Deterministic, offline provider for tests, CI and a no-key demo.

    Replies by echoing the last user message, one word at a time. Trigger words let tests exercise failure
    and slow paths without a network:
      - a message containing "[error]" fails after the first few words (mid-stream failure)
      - a message containing "[slow]" streams slowly, so a test can press Stop part-way
      - "[table]", "[chart]", "[image]", "[choices]" append that structured part after the text
        (the same shapes a tool-backed provider will produce later)
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
        for trigger, part in DEMO_PARTS.items():
            if trigger in last_user:
                yield PartEvent(part)
        prompt_words = sum(len(m.content.split()) for m in messages)
        yield Usage(tokens_in=prompt_words, tokens_out=len(words))
