import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health_reports_unconfigured_services(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "redis_url", None)
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "not_configured", "redis": "not_configured"}


async def test_health_stream_emits_ticks_then_done(client):
    async with client.stream("GET", "/api/v1/health/stream", params={"ticks": 2}) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in res.aiter_text()])
    ticks = [json.loads(l[6:])["n"] for l in body.splitlines() if l.startswith("data:") and '"n"' in l]
    assert ticks == [1, 2]
    assert "event: done" in body
