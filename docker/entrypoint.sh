#!/usr/bin/env sh
set -eu

uv run python - <<'PY'
import os
import time
import psycopg

url = os.getenv("SUPASEBASE_DB_URL")
if not url:
    host = os.getenv("SUPASEBASE_DB_HOST")
    name = os.getenv("SUPASEBASE_DB_NAME")
    user = os.getenv("SUPASEBASE_DB_USER")
    password = os.getenv("SUPASEBASE_DB_PASSWORD")
    port = os.getenv("SUPASEBASE_DB_PORT")
    if all([host, name, user, password, port]):
        url = f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode=disable"

if not url:
    raise SystemExit("Database config is missing. Set SUPASEBASE_DB_URL or SUPASEBASE_DB_* values.")

for attempt in range(1, 61):
    try:
        with psycopg.connect(url, connect_timeout=2):
            print("Database is ready.")
            break
    except Exception:
        if attempt == 60:
            raise SystemExit("Timed out waiting for database.")
        time.sleep(2)
PY

if [ "${AUTO_SEED_DB:-1}" = "1" ]; then
  uv run python /app/docker/seed_db_if_empty.py
fi

if [ "${AUTO_VECTORIZE_TOOLS:-1}" = "1" ]; then
  uv run python /app/docker/vectorize_if_needed.py
fi

exec "$@"
