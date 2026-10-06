from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = None
    redis_url: str | None = None
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Auth. JWT_SECRET has no default on purpose: the app must fail loudly if it is missing.
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # True in production (HTTPS only). False locally so the cookie works over http://localhost.
    cookie_secure: bool = False

    # Language model. "mock" (offline, deterministic) is for local development and tests only: the app refuses to
    # start in production (COOKIE_SECURE=true) with it. "openai_compatible" talks to any OpenAI-style API
    # (OpenRouter, Poe, Gemini, Groq...) using the three settings below.
    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "poolside/laguna-s-2.1:free"
    llm_request_timeout_s: float = 60.0
    # Free tiers throttle often. The SDK waits (exponential backoff, honours Retry-After) and retries the same model.
    llm_max_retries: int = 5
    llm_max_tool_rounds: int = 4  # model -> tools -> model loops allowed per reply
    llm_max_history_messages: int = 40

    @property
    def async_database_url(self) -> str | None:
        """Railway and most hosts provide postgresql://; SQLAlchemy async needs the asyncpg driver."""
        url = self.database_url
        if not url:
            return None
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]
        return url


settings = Settings()
