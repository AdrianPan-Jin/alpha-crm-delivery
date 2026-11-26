from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Company, Contact

ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_uuid_defaults_and_scoping(session):
    c = Company(org_id=ORG, name="杭州云帆科技有限公司")
    session.add(c)
    await session.flush()
    assert isinstance(c.id, uuid.UUID)
    assert c.created_at is not None and c.deleted_at is None
    assert c.status == "active" and c.level == "normal" and c.revenue_cents == 0


@pytest.mark.asyncio
async def test_check_constraints_reject_bad_values(session):
    session.add(Company(org_id=ORG, name="A", level="vip"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    session.add(Contact(org_id=ORG, name="张三", phone="12345"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    session.add(Company(org_id=ORG, name="B", revenue_cents=-1))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_partial_unique_ignores_soft_deleted(session):
    from datetime import datetime, timezone

    first = Company(org_id=ORG, name="同名公司")
    session.add(first)
    await session.flush()

    session.add(Company(org_id=ORG, name="同名公司"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    first.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    session.add(Company(org_id=ORG, name="同名公司"))
    await session.flush()
    alive = (await session.execute(select(Company).where(Company.deleted_at.is_(None)))).scalars().all()
    assert len(alive) == 1


@pytest.mark.asyncio
async def test_external_key_is_unique_per_org(session):
    other_org = uuid.uuid4()
    session.add(Company(org_id=ORG, name="C1", external_key="k-1"))
    await session.flush()
    session.add(Company(org_id=other_org, name="C1", external_key="k-1"))
    await session.flush()
    session.add(Company(org_id=ORG, name="C2", external_key="k-1"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
