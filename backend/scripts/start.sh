#!/bin/sh
# Container entrypoint: apply database migrations, then start the API.
# Migrations are idempotent (Alembic skips what is already applied). If a migration fails,
# `set -e` stops the container, so the deploy is marked failed and the previous version keeps serving.
set -e

if [ -n "$DATABASE_URL" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
else
  echo "DATABASE_URL not set: skipping migrations"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
