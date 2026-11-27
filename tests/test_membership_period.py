"""S2-CRM-003: membership period exclusion (overlapping active memberships).

Maps to the order's acceptance items:

1. upgrade / downgrade round trip, ``alembic check`` zero drift
2. two active overlapping memberships for one company are rejected; the day
   after the previous ``end_date`` is accepted
3. after the previous row is ``terminated`` or soft-deleted, an overlapping
   period is accepted
4. ``end_date < start_date`` is rejected by CHECK

The EXCLUDE constraint needs ``btree_gist`` (contrib).  The full node (PG19,
port 55433) has it; the trimmed local build (PG16, port 55432) does not, so the
whole module skips there instead of pretending to pass.
"""

from __future__ import annotations

import datetime as dt
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


def _has_btree_gist() -> bool:
    with _admin() as conn:
        return conn.execute("SELECT 1 FROM pg_available_extensions WHERE name='btree_gist'").fetchone() is not None


pytestmark = pytest.mark.skipif(
    not _has_btree_gist(), reason="btree_gist (contrib) not available on this PostgreSQL build"
)


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
def mg_db():
    name = f"alpha_mem_{uuid.uuid4().hex[:8]}"
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
def conn(mg_db):
    yield mg_db
    mg_db.rollback()


def _insert(conn, member_no: str, company: uuid.UUID, start: dt.date, end: dt.date, status: str = "active"):
    return conn.execute(
        """
        INSERT INTO crm_membership (org_id, member_no, company_id, status, start_date, end_date, tier)
        VALUES (%s, %s, %s, %s, %s, %s, 'gold')
        RETURNING id
        """,
        (ORG, member_no, company, status, start, end),
    ).fetchone()[0]


def test_upgrade_downgrade_roundtrip_and_zero_drift(mg_db) -> None:
    """AC1: downgrade one step, upgrade again, then ``alembic check``."""
    url = f"postgresql+psycopg://postgres@{PG_HOST}:{PG_PORT}/{mg_db.info.dbname}"
    assert _alembic(url, "downgrade", "-1").returncode == 0
    assert _alembic(url, "upgrade", "head").returncode == 0
    check = _alembic(url, "check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_overlap_rejected(conn):
    company = uuid.uuid4()
    _insert(conn, "M-001", company, dt.date(2026, 1, 1), dt.date(2026, 6, 30))
    with pytest.raises(psycopg.errors.ExclusionViolation):
        _insert(conn, "M-002", company, dt.date(2026, 3, 1), dt.date(2026, 12, 31))


def test_adjacent_period_allowed(conn):
    company = uuid.uuid4()
    _insert(conn, "M-003", company, dt.date(2026, 1, 1), dt.date(2026, 6, 30))
    _insert(conn, "M-004", company, dt.date(2026, 7, 1), dt.date(2026, 12, 31))


def test_overlap_allowed_after_terminated(conn):
    company = uuid.uuid4()
    _insert(conn, "M-005", company, dt.date(2026, 1, 1), dt.date(2026, 6, 30), status="terminated")
    _insert(conn, "M-006", company, dt.date(2026, 3, 1), dt.date(2026, 12, 31))


def test_overlap_allowed_after_soft_delete(conn):
    company = uuid.uuid4()
    conn.execute(
        "INSERT INTO crm_membership (org_id, member_no, company_id, status, start_date, end_date, tier, deleted_at) "
        "VALUES (%s, %s, %s, 'active', %s, %s, 'gold', now())",
        (ORG, "M-007", company, dt.date(2026, 1, 1), dt.date(2026, 6, 30)),
    )
    _insert(conn, "M-008", company, dt.date(2026, 3, 1), dt.date(2026, 12, 31))


def test_end_before_start_rejected(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert(conn, "M-009", uuid.uuid4(), dt.date(2026, 6, 1), dt.date(2026, 1, 1))


def test_single_day_membership_allowed(conn):
    d = dt.date(2026, 5, 5)
    _insert(conn, "M-010", uuid.uuid4(), d, d)
