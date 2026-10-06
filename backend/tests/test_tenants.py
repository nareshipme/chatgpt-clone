import pytest


async def test_two_demo_companies_are_listed_without_signing_in(client):
    r = await client.get("/api/v1/tenants")
    assert r.status_code == 200
    assert {t["id"] for t in r.json()} == {"northwind", "harbor"}
    assert all(set(t) == {"id", "name", "industry"} for t in r.json())


async def test_registering_assigns_the_chosen_company_and_the_planner_role(client, register_user):
    a = await register_user("a@x.com", tenant_id="northwind")
    b = await register_user("b@x.com", tenant_id="harbor")
    assert (a["user"]["tenant_id"], a["user"]["role"]) == ("northwind", "planner")
    assert b["user"]["tenant_id"] == "harbor"
    me = (await client.get("/api/v1/me", headers=b["headers"])).json()
    assert me["tenant_id"] == "harbor"


async def test_company_defaults_to_the_first_demo_tenant(client):
    r = await client.post("/api/v1/auth/register", json={"email": "d@x.com", "password": "a-long-enough-pw", "display_name": "D"})
    assert r.status_code == 201 and r.json()["tenant_id"] == "northwind"


async def test_an_unknown_company_is_rejected_with_a_clear_error(client):
    r = await client.post("/api/v1/auth/register", json={"email": "e@x.com", "password": "a-long-enough-pw", "display_name": "E", "tenant_id": "acme"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unknown_tenant"
    # and no account was created
    login = await client.post("/api/v1/auth/login", json={"email": "e@x.com", "password": "a-long-enough-pw"})
    assert login.status_code == 401


async def test_the_role_cannot_be_chosen_by_the_client(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "f@x.com", "password": "a-long-enough-pw", "display_name": "F", "role": "manager"},
    )
    assert r.status_code == 201 and r.json()["role"] == "planner"  # unknown field ignored


async def test_the_database_rejects_an_invalid_role(migrated_db):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migrated_db)
    async with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(
                text("INSERT INTO users (id, email, password_hash, display_name, role) VALUES ('11111111111111111111111111111111','z@x.com','h','Z','admin')")
            )
    await engine.dispose()
