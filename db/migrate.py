"""Apply db/migrations/*.sql in order, once each.

Usage: DATABASE_URL=postgresql://postgres:postgres@localhost:5432/automations uv run python db/migrate.py
Creates the database if it does not exist (connects to the maintenance db `postgres` to do so).
Dependencies: psycopg (installed by `uv sync` at the repo root).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg

HERE = Path(__file__).resolve().parent
MIGRATIONS = HERE / "migrations"
DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/automations"


def ensure_database(url: str) -> None:
    u = urlparse(url)
    dbname = u.path.lstrip("/")
    admin = url.replace(f"/{dbname}", "/postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone():
            conn.execute(f'CREATE DATABASE "{dbname}"')
            print(f"created database {dbname}")


def applied(conn: psycopg.Connection) -> set[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migration ("
        "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    return {r[0] for r in conn.execute("SELECT version FROM schema_migration")}


def main() -> int:
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    ensure_database(url)
    with psycopg.connect(url) as conn:
        done = applied(conn)
        ran = 0
        for path in sorted(MIGRATIONS.glob("*.sql")):
            version = path.stem
            if version in done:
                continue
            conn.execute(path.read_text(encoding="utf-8"))  # each file wraps itself in BEGIN/COMMIT
            conn.execute("INSERT INTO schema_migration (version) VALUES (%s) ON CONFLICT DO NOTHING", (version,))
            conn.commit()
            print(f"applied {version}")
            ran += 1
        print(f"{ran} migration(s) applied, {len(done)} already present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
