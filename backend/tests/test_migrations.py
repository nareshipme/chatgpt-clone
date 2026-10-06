import sqlalchemy as sa
from alembic import command


def _inspect(url: str):
    sync_url = url.replace("sqlite+aiosqlite", "sqlite")
    return sa.inspect(sa.create_engine(sync_url))


def test_upgrade_creates_users_table(migrated_db):
    insp = _inspect(migrated_db)
    assert "users" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("users")}
    assert set(cols) == {"id", "email", "password_hash", "display_name", "created_at", "updated_at"}
    assert not any(cols[c]["nullable"] for c in cols)
    uniques = [u["column_names"] for u in insp.get_unique_constraints("users")]
    assert ["email"] in uniques


def test_downgrade_removes_users_table(migrated_db, alembic_cfg):
    command.downgrade(alembic_cfg, "base")
    assert "users" not in _inspect(migrated_db).get_table_names()


def test_models_match_migrations(migrated_db, alembic_cfg):
    """Fails if someone changes a model without writing a migration (alembic check raises)."""
    command.check(alembic_cfg)
