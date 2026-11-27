"""crm_interaction acceptance (S2-CRM-004).

Acceptance mapping:
1. upgrade / downgrade round trip, ``alembic check`` reports no drift
2. ``duration_minutes=1441`` and empty / 5001-char summaries are rejected by CHECK
3. after 10k fictional interactions, the "latest 20 for one company" query uses
   ``ix_crm_interaction_company`` (EXPLAIN captured in README)
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import errors as pg_errors
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")
SITE = uuid.UUID("22222222-2222-2222-2222-222222222222")
PG_ADMIN = dict(host="127.0.0.1", port=55432, user="postgres", dbname="postgres")


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=240,
        env={**os.environ, "DATABASE_URL": url},
    )


@pytest.fixture(scope="module")
def mig_db() -> str:
    name = f"alpha_int_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = f"postgresql+psycopg://postgres@127.0.0.1:55432/{name}"
    try:
        assert _alembic(url, "upgrade", "head").returncode == 0
        yield url
    finally:
        with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture()
def db(mig_db: str):
    """Sync psycopg connection to the migrated database, one per test."""
    dsn = mig_db.replace("postgresql+psycopg://", "postgresql://")
    conn = psycopg.connect(dsn, autocommit=False)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _company(conn, name: str = "虚构企业A") -> uuid.UUID:
    cid = uuid.uuid4()
    conn.execute(
        "INSERT INTO companies (id, org_id, name, level, status) VALUES (%s,%s,%s,'normal','active')",
        (cid, ORG, name),
    )
    return cid


def _insert(conn, company_id, **kw):
    row = dict(
        org_id=ORG,
        site_id=SITE,
        company_id=company_id,
        type="visit",
        occurred_at="2026-11-01T10:00:00+08:00",
        summary="虚构到访纪要",
        source="manual",
    )
    row.update(kw)
    cols = ", ".join(row)
    vals = ", ".join(["%s"] * len(row))
    conn.execute(f"INSERT INTO crm_interaction ({cols}) VALUES ({vals})", tuple(row.values()))


def test_upgrade_downgrade_roundtrip_and_check(mig_db: str) -> None:
    assert _alembic(mig_db, "check").returncode == 0
    down = _alembic(mig_db, "downgrade", "0005")
    assert down.returncode == 0, down.stderr[-2000:]
    with psycopg.connect(mig_db.replace("postgresql+psycopg://", "postgresql://")) as c:
        exists = c.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name='crm_interaction'"
        ).fetchone()
        assert exists is None
    up = _alembic(mig_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr[-2000:]
    assert _alembic(mig_db, "check").returncode == 0



def _rejected(conn, **kw):
    """Insert inside a savepoint; a CHECK/FK violation rolls the savepoint back."""
    conn.execute("SAVEPOINT sp")
    try:
        _insert(conn, kw.pop("company_id"), **kw)
    except pg_errors.IntegrityError:
        conn.execute("ROLLBACK TO SAVEPOINT sp")
        return True
    conn.execute("RELEASE SAVEPOINT sp")
    return False


def test_valid_row_accepted(db) -> None:
    cid = _company(db)
    _insert(db, cid, duration_minutes=45, next_action="再次回访", next_action_due="2026-11-20")
    assert db.execute("SELECT count(*) FROM crm_interaction").fetchone()[0] == 1


@pytest.mark.parametrize("minutes", [1441, -1])
def test_duration_out_of_range_rejected(db, minutes) -> None:
    cid = _company(db)
    assert _rejected(db, company_id=cid, duration_minutes=minutes) is True
    assert _rejected(db, company_id=cid, duration_minutes=1440) is False


@pytest.mark.parametrize("summary", ["", "x" * 5001])
def test_summary_length_rejected(db, summary) -> None:
    cid = _company(db)
    assert _rejected(db, company_id=cid, summary=summary) is True
    assert _rejected(db, company_id=cid, summary="x" * 5000) is False


def test_enum_and_default_rejected(db) -> None:
    cid = _company(db)
    assert _rejected(db, company_id=cid, type="fax") is True
    assert _rejected(db, company_id=cid, source="unknown") is True
    # source 默认 manual
    db.execute(
        "INSERT INTO crm_interaction (org_id, site_id, company_id, type, occurred_at, summary) "
        "VALUES (%s,%s,%s,'call',now(),'默认来源')",
        (ORG, SITE, cid),
    )
    assert db.execute("SELECT source FROM crm_interaction").fetchone()[0] == "manual"


def test_latest_20_uses_company_index(db) -> None:
    cid = _company(db, "虚构企业-索引")
    db.execute(
        "INSERT INTO crm_interaction (org_id, site_id, company_id, type, occurred_at, summary, source) "
        "SELECT %s, %s, %s, 'call', now() - (g || ' minutes')::interval, '虚构纪要' || g, 'system' "
        "FROM generate_series(1, 10000) AS g",
        (ORG, SITE, cid),
    )
    db.execute("ANALYZE crm_interaction")
    plan = db.execute(
        "EXPLAIN SELECT id, summary FROM crm_interaction "
        "WHERE org_id = %s AND company_id = %s ORDER BY occurred_at DESC LIMIT 20",
        (ORG, cid),
    ).fetchall()
    text_plan = "\n".join(r[0] for r in plan)
    assert "ix_crm_interaction_company" in text_plan, text_plan
