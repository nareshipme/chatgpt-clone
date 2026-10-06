from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.db.session import get_db
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def alembic_cfg() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture
def db_url(tmp_path, monkeypatch) -> str:
    """A throwaway SQLite database; settings are pointed at it for the duration of the test."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    return url


@pytest.fixture
def migrated_db(db_url, alembic_cfg) -> str:
    """Database with all migrations applied (sync fixture: Alembic runs its own event loop)."""
    command.upgrade(alembic_cfg, "head")
    return db_url


TEST_JWT_SECRET = "test-secret-with-enough-length-for-hs256-0123456789"


@pytest.fixture
async def client(migrated_db, monkeypatch):
    """HTTP client against the real app, wired to the migrated throwaway database."""
    monkeypatch.setattr(settings, "jwt_secret", TEST_JWT_SECRET)
    engine = create_async_engine(migrated_db)

    async def _get_db():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()
