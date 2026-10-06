import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("sqlite+aiosqlite:///test.db", "sqlite+aiosqlite:///test.db"),
        (None, None),
    ],
)
def test_async_database_url(raw, expected):
    assert Settings(database_url=raw, _env_file=None).async_database_url == expected
