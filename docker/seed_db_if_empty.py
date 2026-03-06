import os
import psycopg
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.db import init_db, seed_db


def _table_has_rows(conn: psycopg.Connection, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(f"SELECT EXISTS (SELECT 1 FROM {table} LIMIT 1) AS has_rows;")
        row = cur.fetchone()
        return bool(row[0]) if row else False


def main() -> None:
    db_url = os.getenv("SUPASEBASE_DB_URL")
    if not db_url:
        return

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.products') IS NOT NULL;")
            exists = bool(cur.fetchone()[0])

        if exists and _table_has_rows(conn, "products"):
            print("Products table already seeded. Skipping DB seed.")
            return

    print("Seeding database from data/products.json ...")
    os.chdir(PROJECT_ROOT / "data")
    init_db()
    seed_db()
    print("Database seed complete.")


if __name__ == "__main__":
    main()
