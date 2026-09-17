FROM python:3.11-slim

WORKDIR /app

COPY telegram-bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram-bridge/app/ ./app/
COPY tools/ ./tools/
COPY telegram-bridge/migrations/ ./migrations/
COPY telegram-bridge/alembic.ini .

EXPOSE 8000

CMD ["sh", "-c", "python -c 'from app.config import settings' || { echo 'FATAL: missing/invalid required env vars (BOT_TOKEN / CHAT_ID / ADMIN_CHAT_ID / SECRET_KEY / WEBHOOK_SECRET_TOKEN). Set them in Render Dashboard -> Service -> Environment, then redeploy.' >&2; exit 1; }; alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
