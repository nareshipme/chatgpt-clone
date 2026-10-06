import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

router = APIRouter(tags=["health"])


async def _check_db() -> str:
    url = settings.async_database_url
    if not url:
        return "not_configured"
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as conn:
                await conn.execute(text("select 1"))
        return "ok"
    except Exception:
        return "error"
    finally:
        await engine.dispose()


async def _check_redis() -> str:
    if not settings.redis_url:
        return "not_configured"
    client = Redis.from_url(settings.redis_url)
    try:
        async with asyncio.timeout(3):
            await client.ping()
        return "ok"
    except Exception:
        return "error"
    finally:
        await client.aclose()


@router.get("/health")
async def health() -> dict:
    db, cache = await asyncio.gather(_check_db(), _check_redis())
    return {"status": "ok", "db": db, "redis": cache}


@router.get("/health/stream")
async def health_stream(ticks: int = 8) -> StreamingResponse:
    """SSE smoke test: proves streaming works end to end through Nginx / the platform proxy."""

    async def gen() -> AsyncIterator[str]:
        yield ": connected\n\n"
        for i in range(1, min(ticks, 30) + 1):
            await asyncio.sleep(1)
            yield f"event: tick\ndata: {json.dumps({'n': i})}\n\n"
        yield f"event: done\ndata: {json.dumps({'ticks': min(ticks, 30)})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
