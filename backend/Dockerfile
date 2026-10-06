FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

# Railway injects PORT (default 8000 locally). The script runs migrations, then starts uvicorn.
CMD ["sh", "scripts/start.sh"]
