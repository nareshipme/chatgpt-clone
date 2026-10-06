from app.config import settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider


def validate_llm_config() -> None:
    """Fail at startup, not on the first chat, if the LLM is misconfigured. There is no silent fallback to the mock."""
    if settings.llm_provider == "mock":
        if settings.cookie_secure:
            raise RuntimeError("LLM_PROVIDER=mock is not allowed in production. Set LLM_PROVIDER=openai_compatible.")
        return
    if settings.llm_provider != "openai_compatible":
        raise RuntimeError(f"Unknown LLM_PROVIDER '{settings.llm_provider}' (use openai_compatible or mock).")
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is required when LLM_PROVIDER=openai_compatible.")


def build_provider() -> LLMProvider:
    validate_llm_config()
    if settings.llm_provider == "mock":
        return MockProvider()
    from app.llm.openai_compat import OpenAICompatProvider  # lazy: the mock path needs no network client

    return OpenAICompatProvider(
        api_key=settings.llm_api_key or "",
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_s=settings.llm_request_timeout_s,
        max_retries=settings.llm_max_retries,
    )


def get_llm_provider() -> LLMProvider:
    """FastAPI dependency. Tests override it with a MockProvider they control."""
    return build_provider()
