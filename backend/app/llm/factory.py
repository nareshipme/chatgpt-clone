from app.config import settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider


def build_provider() -> LLMProvider:
    """Pick the backend from configuration. A missing key falls back to the mock instead of crashing,
    so the app always starts; the chat UI can tell the user it is in demo mode."""
    if settings.llm_provider == "poe" and settings.poe_api_key:
        from app.llm.poe import PoeProvider  # imported lazily: the mock path needs no network client

        return PoeProvider(
            api_key=settings.poe_api_key,
            base_url=settings.poe_base_url,
            model=settings.poe_model,
            timeout_s=settings.llm_request_timeout_s,
        )
    return MockProvider()


def get_llm_provider() -> LLMProvider:
    """FastAPI dependency. Tests override it with a MockProvider they control."""
    return build_provider()
