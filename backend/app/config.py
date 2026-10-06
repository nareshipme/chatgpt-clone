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
