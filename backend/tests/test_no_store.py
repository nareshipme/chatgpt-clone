async def test_api_responses_are_never_cacheable(client, register_user):
    a = await register_user("a@example.com")
    for res in (
        await client.get("/api/v1/me", headers=a["headers"]),  # 200, per-user data
        await client.get("/api/v1/me"),  # 401 error response
        await client.get("/api/v1/conversations", headers=a["headers"]),
        await client.get("/api/v1/health"),
    ):
        assert res.headers["cache-control"] == "no-store"


async def test_the_sse_stream_keeps_its_own_cache_header(client):
    async with client.stream("GET", "/api/v1/health/stream", params={"ticks": 1}) as res:
        assert res.headers["cache-control"] == "no-cache"
        await res.aread()


async def test_non_api_paths_are_untouched(client):
    res = await client.get("/not-an-api-path")
    assert "cache-control" not in res.headers
