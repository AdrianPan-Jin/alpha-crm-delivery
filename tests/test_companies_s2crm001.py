"""S2-CRM-001: enterprise table — uscc uniqueness, lifecycle, health score, trgm.

Maps to the order's acceptance items:

1. upgrade / downgrade round trip, ``alembic check`` shows no drift
2. two live enterprises with the same uscc in one org are rejected; after
   soft-deleting one, a new insert succeeds
3. health_score 101 / -1 and an unknown lifecycle_status are rejected by CHECK
4. ``EXPLAIN`` of ``name ILIKE '%example%'`` hits the GIN trigram index
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
PG_HOST = os.environ.get("PG_HOST", "127.0.0.1")
PG_PORT = int(os.environ.get("PG_PORT", "55432"))
ORG = "11111111-1111-1111-1111-111111111111"


def _admin():
    return psycopg.connect(host=PG_HOST, port=PG_PORT, user="postgres", dbname="postgres", autocommit=True)


def _has_trgm() -> bool:
    with _admin() as conn:
        return conn.execute("SELECT 1 FROM pg_available_extensions WHERE name='pg_trgm'").fetchone() is not None


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "DATABASE_URL": url},
    )


@pytest.fixture(scope="module")
def db():
    name = f"alpha_co_{uuid.uuid4().hex[:8]}"
    with _admin() as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = f"postgresql+psycopg://postgres@{PG_HOST}:{PG_PORT}/{name}"
    try:
        r = _alembic(url, "upgrade", "head")
        assert r.returncode == 0, r.stdout + r.stderr
        with psycopg.connect(host=PG_HOST, port=PG_PORT, user="postgres", dbname=name) as conn:
            yield conn
    finally:
        with _admin() as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture()
def conn(db):
    yield db
    db.rollback()


def _company(conn, uscc: str | None = None, health: int | None = None, lifecycle: str = "prospect"):
    code = uscc or uuid.uuid4().hex[:18].upper()
    return conn.execute(
        "INSERT INTO companies (org_id, name, unified_credit_code, health_score, lifecycle_status) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (ORG, f"示例企业{uuid.uuid4().hex[:6]}（虚构）", code, health, lifecycle),
    ).fetchone()[0]


def test_upgrade_downgrade_roundtrip_and_zero_drift(db) -> None:
    url = f"postgresql+psycopg://postgres@{PG_HOST}:{PG_PORT}/{db.info.dbname}"
    assert _alembic(url, "downgrade", "-1").returncode == 0
    assert _alembic(url, "upgrade", "head").returncode == 0
    check = _alembic(url, "check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_duplicate_uscc_rejected_and_reusable_after_soft_delete(conn):
    uscc = "91330100MA2AB3CD4E"
    first = _company(conn, uscc=uscc)
    # nested transaction = SAVEPOINT, so the failed insert does not poison the outer tx
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            _company(conn, uscc=uscc)
    conn.execute("UPDATE companies SET deleted_at = now() WHERE id = %s", (first,))
    _company(conn, uscc=uscc)  # after soft delete the code is free again


@pytest.mark.parametrize("bad", [101, -1])
def test_health_score_out_of_range_rejected(conn, bad):
    with pytest.raises(psycopg.errors.CheckViolation):
        _company(conn, health=bad)


def test_health_score_boundaries_accepted(conn):
    assert _company(conn, health=0)
    assert _company(conn, health=100)


def test_lifecycle_enum_rejected(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        _company(conn, lifecycle="vip")


@pytest.mark.skipif(not _has_trgm(), reason="pg_trgm not available on this PostgreSQL build")
def test_ilike_uses_trigram_index(conn):
    # A tiny table is scanned sequentially no matter what: "example" must be a RARE
    # term for the planner to prefer the trigram index, so seed 100k rows and keep
    # only a handful of them containing the search term.
    with conn.transaction():
        conn.execute(
            "INSERT INTO companies (org_id, name) "
            "SELECT %s, '示例企业 ' || g FROM generate_series(1, 100000) AS g",
            (ORG,),
        )
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO companies (org_id, name) VALUES (%s, %s)",
                [(ORG, f"Acme Example Hub {i}") for i in range(5)],
            )
    conn.execute("ANALYZE companies")
    plan = " ".join(
        row[0]
        for row in conn.execute(
            "EXPLAIN SELECT id FROM companies WHERE name ILIKE '%example%'"
        ).fetchall()
    )
    assert "ix_companies_name_trgm" in plan, plan
