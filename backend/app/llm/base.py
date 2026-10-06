"""The contract between the chat service and any language-model backend.

The service only knows this interface. Swapping Poe for Azure OpenAI, or for a mock in tests, is a
configuration change, not a code change.
"""
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    """One turn of history sent to the model. role is 'system', 'user' or 'assistant'."""

    role: str
    content: str


@dataclass(frozen=True)
class TextDelta:
    """A fragment of the assistant's reply, in order. Concatenating all deltas gives the full text."""

    text: str


@dataclass(frozen=True)
class Usage:
    """Token counts, emitted once at the end when the backend reports them."""

    tokens_in: int
    tokens_out: int


LLMEvent = TextDelta | Usage


class LLMError(Exception):
    """The model backend failed. `code` is stable and safe to show; `message` is user-presentable.

    Never put provider internals, URLs or keys in either field.
    """

    def __init__(self, code: str = "llm_unavailable", message: str = "The assistant is unavailable right now."):
        super().__init__(message)
        self.code = code
        self.message = message


class LLMProvider(Protocol):
    name: str

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[LLMEvent]:
        """Yield TextDelta events (then optionally one Usage). Raise LLMError on failure.

        The consumer may stop early (user pressed Stop); implementations must clean up when the async
        iterator is closed.
        """
        ...
