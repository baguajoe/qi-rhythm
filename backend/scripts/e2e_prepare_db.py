"""Reset the end-to-end test database: create it if missing, migrate from scratch, seed rhythms.

Usage (from backend/):
    DATABASE_URL=postgresql+psycopg://qi:qi@localhost:5432/qi_rhythm_e2e \\
        python scripts/e2e_prepare_db.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import normalize_db_url  # noqa: E402


def ensure_database(url: str) -> None:
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    name = parsed.path.lstrip("/")
    admin = parsed._replace(path="/postgres").geturl()
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{name}"')
    with psycopg.connect(parsed.geturl(), autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")


def main() -> None:
    url = normalize_db_url(os.environ["DATABASE_URL"])
    if "e2e" not in url:
        sys.exit("Refusing to reset a database whose name does not contain 'e2e'.")
    ensure_database(url)
    from flask_migrate import upgrade

    from app import create_app
    from app.seed import seed_library

    app = create_app()
    with app.app_context():
        upgrade(directory=str(Path(__file__).resolve().parent.parent / "migrations"))
        g, r = seed_library()
    print(f"e2e database ready: {g} genres, {r} rhythms")


if __name__ == "__main__":
    main()
