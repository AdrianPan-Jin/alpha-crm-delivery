"""Contract table acceptance (S2-CRM-007).

Each test maps to one acceptance item of the order:

1. upgrade / downgrade round trip, ``alembic check`` reports no drift
2. same ``contract_no`` rejected per org, reusable after soft delete
3. ``status='active'`` with ``esign_status<>'signed'`` rejected by CHECK
4. ``crm_membership.contract_id`` FK exists after upgrade and is gone after
   downgrade
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")
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
    """Dedicated database for migration round-trip checks."""
    name = f"alpha_mig_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = f"postgresql+psycopg://postgres@127.0.0.1:55432/{name}"
    try:
        assert _alembic(url, "upgrade", "head").returncode == 0
        yield url
    finally:
        with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


async def _company(session) -> uuid.UUID:
    from app.models import Company

    cid = uuid.uuid4()
    session.add(Company(id=cid, org_id=ORG, name=f"示例企业{cid.hex[:6]}（虚构）", level="normal", status="active"))
    await session.flush()
    return cid


def test_upgrade_downgrade_roundtrip_and_check(mig_db: str) -> None:
    """AC1: upgrade head -> downgrade -1 -> upgrade head, then no drift."""
    assert _alembic(mig_db, "downgrade", "-1").returncode == 0
    assert _alembic(mig_db, "upgrade", "head").returncode == 0
    check = _alembic(mig_db, "check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_membership_fk_added_and_removed(mig_db: str) -> None:
    """AC4: the FK is created by the migration and dropped by its downgrade."""
    with psycopg.connect(host="127.0.0.1", port=55432, user="postgres", dbname=mig_db.rsplit("/", 1)[-1]) as conn:
        row = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname = 'fk_membership_contract'").fetchone()
        assert row[0] == 1
    # the contract migration is 0004, so downgrade to 0003 to drop its FK
    assert _alembic(mig_db, "downgrade", "0003").returncode == 0
    with psycopg.connect(host="127.0.0.1", port=55432, user="postgres", dbname=mig_db.rsplit("/", 1)[-1]) as conn:
        row = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname = 'fk_membership_contract'").fetchone()
        assert row[0] == 0
    assert _alembic(mig_db, "upgrade", "head").returncode == 0


async def test_duplicate_contract_no_rejected(session) -> None:
    """AC2: two live contracts with the same number in one org are rejected."""
    from app.models_contract import Contract

    company_id = await _company(session)
    no = "HT-2026-0001"
    session.add(Contract(org_id=ORG, company_id=company_id, contract_no=no, party_a_snapshot={"name": "甲方（虚构）"}))
    await session.flush()
    session.add(Contract(org_id=ORG, company_id=company_id, contract_no=no))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_contract_no_reusable_after_soft_delete(session) -> None:
    """AC2: after soft delete the number can be reused."""
    from app.models_contract import Contract

    company_id = await _company(session)
    no = "HT-2026-0002"
    first = Contract(org_id=ORG, company_id=company_id, contract_no=no)
    session.add(first)
    await session.flush()
    await session.execute(text("UPDATE crm_contract SET deleted_at = now() WHERE id = :id"), {"id": first.id})
    session.add(Contract(org_id=ORG, company_id=company_id, contract_no=no))
    await session.flush()


async def test_active_requires_signed(session) -> None:
    """AC3: active without a signed e-sign state is rejected."""
    from app.models_contract import Contract

    company_id = await _company(session)
    session.add(
        Contract(org_id=ORG, company_id=company_id, contract_no="HT-2026-0003", status="active", esign_status="pending")
    )
    with pytest.raises(IntegrityError):
        await session.flush()
