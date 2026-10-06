# ChatGPT Clone: agent context

Full stack ChatGPT clone for a 48-hour assignment. **Source of truth: `docs/PLAN.md`** (scope, HLD, LLD, milestones). The original brief is `docs/assignment.pdf`.

## Stack
FastAPI + SQLAlchemy 2 (async) + PostgreSQL + Alembic + Redis; React 18 + TypeScript + Vite + Material UI; SSE streaming; JWT access token + httpOnly refresh cookie; Docker Compose.

## Rules for agents
- Work in vertical slices (S0-S8 in the plan); one story at a time, tests first where practical.
- Keep the backend layered: routers -> services -> repositories -> models. No DB access in routers.
- Every query is scoped to the current user. Add an ownership test for each new resource.
- Messages are typed JSON "parts" (text, table, chart, image, actions). Follow the SSE contract in `docs/PLAN.md` section 4.5.
- Real LLM = Poe API via the `openai` SDK (`POE_BASE_URL=https://api.poe.com/v1`, key in `POE_API_KEY`). `MockProvider` is only for tests/CI/no-key demo mode. Poe ignores `strict` tool schemas and has no JSON-schema outputs: validate tool args with Pydantic and build message parts server-side from tool results. Never print, log or commit the key.
- No secrets in git; use `.env` (ignored) and keep `.env.example` current.
- Small, clearly labeled commits. Update README and ADRs when decisions change.

## Deployment
All services on Railway (web = Nginx serving the React build and proxying /api to api over the private network; api; Postgres; Redis). No Vercel. See `docs/PLAN.md` section 14. Secrets only in Railway variables. Nginx must not buffer SSE.

## Domain pack (Blue Yonder)
Optional "Supply Chain Copilot" layer in `docs/PLAN.md` section 12: personas, domain tools over fictional data, approval actions + audit, tenant scoping. Keep it thin and behind the core clone. Use generic names and fictional data only (no Blue Yonder logos, product names or customer data). Numbers in answers must come from tool results.

## BMAD
Installed in `_bmad/`; skills in `.claude/skills/`. Start with `bmad-help`. Planning outputs go to `_bmad-output/`.
