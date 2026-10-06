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


def test_refresh_tokens_table_has_hash_unique_and_user_foreign_key(migrated_db):
    insp = _inspect(migrated_db)
    cols = {c["name"] for c in insp.get_columns("refresh_tokens")}
    assert cols == {"id", "user_id", "family_id", "token_hash", "expires_at", "revoked_at", "created_at"}
    assert ["token_hash"] in [u["column_names"] for u in insp.get_unique_constraints("refresh_tokens")]
    fks = insp.get_foreign_keys("refresh_tokens")
    assert fks[0]["referred_table"] == "users" and fks[0]["options"].get("ondelete") == "CASCADE"


def test_conversations_table_is_indexed_for_the_per_user_listing(migrated_db):
    insp = _inspect(migrated_db)
    cols = {c["name"]: c for c in insp.get_columns("conversations")}
    assert set(cols) == {"id", "user_id", "title", "archived", "created_at", "updated_at"}
    index_cols = [i["column_names"] for i in insp.get_indexes("conversations")]
    assert ["user_id", "updated_at"] in index_cols
    fk = insp.get_foreign_keys("conversations")[0]
    assert fk["referred_table"] == "users" and fk["options"].get("ondelete") == "CASCADE"
