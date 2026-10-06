import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.services import auth_service
from app.services.auth_service import EmailTakenError, InvalidCredentialsError


@pytest.fixture
async def session(migrated_db):
    engine = create_async_engine(migrated_db)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


async def _register(session, email="Ada@Example.com", password="a-long-enough-pw"):
    return await auth_service.register(session, email=email, password=password, display_name="Ada")


async def test_register_stores_a_hash_and_lowercased_email(session):
    user = await _register(session)
    assert user.email == "ada@example.com"
    assert user.password_hash.startswith("$argon2id$") and "a-long-enough-pw" not in user.password_hash


async def test_duplicate_email_is_rejected_case_insensitively(session):
    await _register(session, email="ada@example.com")
    with pytest.raises(EmailTakenError):
        await _register(session, email="ADA@example.com")


async def test_authenticate_succeeds_with_correct_password(session):
    created = await _register(session)
    user = await auth_service.authenticate(session, email="  ada@EXAMPLE.com ", password="a-long-enough-pw")
    assert user.id == created.id


async def test_wrong_password_and_unknown_email_fail_identically(session):
    await _register(session)
    with pytest.raises(InvalidCredentialsError) as wrong:
        await auth_service.authenticate(session, email="ada@example.com", password="nope-nope-nope")
    with pytest.raises(InvalidCredentialsError) as unknown:
        await auth_service.authenticate(session, email="ghost@example.com", password="nope-nope-nope")
    assert wrong.value.message == unknown.value.message and wrong.value.code == unknown.value.code


async def test_unknown_email_still_runs_a_password_verification(session, monkeypatch):
    calls = []
    real = auth_service.verify_password
    monkeypatch.setattr(auth_service, "verify_password", lambda h, p: calls.append(1) or real(h, p))
    with pytest.raises(InvalidCredentialsError):
        await auth_service.authenticate(session, email="ghost@example.com", password="whatever-pw-1")
    assert calls == [1]  # constant-time-ish: a miss does the same hashing work as a wrong password
