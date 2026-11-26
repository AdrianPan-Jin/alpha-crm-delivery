from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid

import psycopg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

if sys.platform == "win32":  # psycopg async needs the selector loop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PG_ADMIN = dict(host="127.0.0.1", port=55432, user="postgres", dbname="postgres")


@pytest.fixture(scope="session")
def db_url() -> str:
    name = f"alpha_t_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = f"postgresql+psycopg://postgres@127.0.0.1:55432/{name}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", os.environ.get("ALEMBIC_REV", "head")],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
    )
    try:
        yield url
    finally:
        with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest_asyncio.fixture
async def session(db_url: str):
    from app.db import make_engine, make_sessionmaker

    engine = make_engine(db_url)
    factory = make_sessionmaker(engine)
    async with factory() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture(scope="module")
def rc_db() -> str:
    """Isolated database for the reconciliation tests (the fixtures wipe tables)."""
    name = f"alpha_rc_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = f"postgresql+psycopg://postgres@127.0.0.1:55432/{name}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
    )
    try:
        yield url
    finally:
        with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
