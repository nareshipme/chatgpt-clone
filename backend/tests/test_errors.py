import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from app.errors import ConflictError, RequestIdMiddleware, register_error_handlers
from app.main import app as real_app


class Payload(BaseModel):
    password: str = Field(min_length=10)


def _test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    @app.post("/echo")
    async def echo(body: Payload):
        return {"ok": True}

    @app.get("/conflict")
    async def conflict():
        raise ConflictError("Already exists")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=_test_app(), raise_app_exceptions=False), base_url="http://t") as c:
        yield c


async def test_app_error_uses_unified_shape_with_request_id(client):
    res = await client.get("/conflict")
    body = res.json()["error"]
    assert res.status_code == 409
    assert body["code"] == "conflict" and body["message"] == "Already exists"
    assert body["requestId"] == res.headers["x-request-id"]


async def test_validation_error_does_not_echo_the_submitted_password(client):
    res = await client.post("/echo", json={"password": "short"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert res.json()["error"]["details"][0]["field"] == "password"
    detail = res.json()["error"]["details"][0]
    assert set(detail) == {"field", "message"}  # no "input" key, so the submitted value is never echoed
    assert '"short"' not in res.text


async def test_unexpected_error_hides_internals(client):
    res = await client.get("/boom")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in res.text


async def test_unknown_route_returns_not_found_shape():
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://t") as c:
        res = await c.get("/nope")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"
    assert "x-request-id" in res.headers
