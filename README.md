# ChatGPT Clone

Full stack ChatGPT-style app (FastAPI + React). Status: **deployment skeleton** (health check, SSE smoke test, Nginx proxy, Dockerfiles). Features are added per `docs/PLAN.md`.

## Run locally (Docker)
```
docker compose up --build
```
Open http://localhost:3000. The page shows API health and an SSE streaming test.

## Run locally (without Docker)
```
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev    # http://localhost:5173, proxies /api to :8000
```

## Deploy (Railway)
Services: `web` (root `/frontend`), `api` (root `/backend`), Postgres, Redis. See `docs/PLAN.md` section 14.
- `api`: variables `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`; healthcheck `/api/v1/health`.
- `web`: variable `API_UPSTREAM=http://api.railway.internal:<api port>`; only `web` gets a public domain.

Never commit secrets: use `.env` locally (git-ignored) and Railway variables in production. See `.env.example`.
