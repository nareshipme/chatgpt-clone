from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.config import settings

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
