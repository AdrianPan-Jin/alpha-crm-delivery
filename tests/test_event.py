"""Event signup domain acceptance (S3-MINI-046).

Acceptance mapping:

1. schema-level: ``alembic check`` reports no drift after the upgrade
2. one live ``confirmed`` signup per (event, member); re-signing after a
   cancel is allowed
3. one live e-ticket per signup, ticket numbers unique per org
4. check-in is unique per signup and rejects unknown methods
5. ``form_snapshot`` keeps ordinary JSON; ``has_contact_keys`` flags direct
   contact identifiers
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
    name = f"alpha_ev_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = f"postgresql+psycopg://postgres@127.0.0.1:55432/{name}"
    try:
        assert _alembic(url, "upgrade", "head").returncode == 0
        yield url
    finally:
        with psycopg.connect(**PG_ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def test_schema_has_no_drift(mig_db: str) -> None:
    """AC1: upgrade head -> downgrade -1 -> upgrade head, then no drift."""
    assert _alembic(mig_db, "downgrade", "-1").returncode == 0
    assert _alembic(mig_db, "upgrade", "head").returncode == 0
    check = _alembic(mig_db, "check")
    assert check.returncode == 0, check.stdout + check.stderr


async def _signup(session, event_id: uuid.UUID, member_id: uuid.UUID, status: str = "confirmed"):
    from app.models_event import EventSignup

    row = EventSignup(org_id=ORG, event_id=event_id, member_id=member_id, status=status)
    session.add(row)
    return row


async def test_duplicate_confirmed_signup_rejected(session) -> None:
    """AC2: the same member cannot hold two live confirmed signups."""
    event_id, member_id = uuid.uuid4(), uuid.uuid4()
    await _signup(session, event_id, member_id)
    await session.flush()
    await _signup(session, event_id, member_id)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_resign_after_cancel_allowed(session) -> None:
    """AC2: a cancelled signup frees the unique slot."""
    event_id, member_id = uuid.uuid4(), uuid.uuid4()
    first = await _signup(session, event_id, member_id, status="cancelled")
    await session.flush()
    second = await _signup(session, event_id, member_id)
    await session.flush()
    assert second.id != first.id


async def test_duplicate_ticket_rejected_and_reusable_after_soft_delete(session) -> None:
    """AC3: one live ticket per signup; a soft-deleted ticket frees the slot."""
    from app.models_event import EventTicket

    signup = await _signup(session, uuid.uuid4(), uuid.uuid4())
    await session.flush()
    ticket = EventTicket(org_id=ORG, signup_id=signup.id, ticket_no="TK-0001")
    session.add(ticket)
    await session.flush()
    session.add(EventTicket(org_id=ORG, signup_id=signup.id, ticket_no="TK-0002"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    signup = await _signup(session, uuid.uuid4(), uuid.uuid4())
    await session.flush()
    ticket = EventTicket(org_id=ORG, signup_id=signup.id, ticket_no="TK-0003")
    session.add(ticket)
    await session.flush()
    await session.execute(text("UPDATE event_tickets SET deleted_at = now() WHERE id = :id"), {"id": ticket.id})
    session.add(EventTicket(org_id=ORG, signup_id=signup.id, ticket_no="TK-0004"))
    await session.flush()


async def test_checkin_unique_and_method_check(session) -> None:
    """AC4: check-in unique per signup, unknown methods rejected."""
    from app.models_event import EventCheckin

    signup = await _signup(session, uuid.uuid4(), uuid.uuid4())
    await session.flush()
    session.add(EventCheckin(org_id=ORG, signup_id=signup.id))
    await session.flush()
    session.add(EventCheckin(org_id=ORG, signup_id=signup.id))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    signup = await _signup(session, uuid.uuid4(), uuid.uuid4())
    await session.flush()
    session.add(EventCheckin(org_id=ORG, signup_id=signup.id, method="nfc"))
    with pytest.raises(IntegrityError):
        await session.flush()


def test_contact_keys_helper() -> None:
    """AC5: the helper only flags direct contact identifiers."""
    from app.models_event import has_contact_keys

    assert has_contact_keys({"phone": "13800000000"}) is True
    assert has_contact_keys({"email": "a@example.com"}) is True
    assert has_contact_keys({"wechat": "wx_id"}) is True
    assert has_contact_keys({"size": "XL", "note": "需要素食"}) is False
    assert has_contact_keys({}) is False
