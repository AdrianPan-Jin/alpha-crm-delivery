"""CRM contract model (S2-CRM-007).

Adds ``crm_contract``: contract_no unique per org among live rows, party
snapshots, e-sign status, and a state-consistency CHECK (active requires
signed).  Money is stored in cents; every business table carries the unified
seven columns (id/org_id/site_id/created_at/created_by/updated_at/deleted_at).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import Timestamped, Tenant, UUIDPk


class Contract(Base, UUIDPk, Tenant, Timestamped):
    __tablename__ = "crm_contract"

    contract_no: Mapped[str] = mapped_column(String(32), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    party_a_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    party_b_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'draft'"))
    esign_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_contract_org_no_alive",
            "org_id",
            "contract_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_contract_company_status", "company_id", "status"),
        CheckConstraint("status IN ('draft','active','terminated')", name="ck_contract_status"),
        CheckConstraint("esign_status IN ('pending','signed','void')", name="ck_contract_esign_status"),
        CheckConstraint(
            "NOT (status = 'active' AND esign_status <> 'signed')",
            name="ck_contract_active_requires_signed",
        ),
        CheckConstraint("amount_cents >= 0", name="ck_contract_amount_nonneg"),
        CheckConstraint("length(btrim(contract_no)) > 0", name="ck_contract_no_nonempty"),
    )


class Membership(Base, UUIDPk, Tenant, Timestamped):
    """Minimal membership table so the contract FK can be exercised locally.

    The buyer's project owns the full ``crm_membership`` (tiers, periods,
    overlap exclusion).  This model only declares the column the contract
    migration links to, and is created only when the table is absent.
    """

    __tablename__ = "crm_membership"

    member_no: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("crm_contract.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tier: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'normal'"))
    starts_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_membership_org_no_alive",
            "org_id",
            "member_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("tier IN ('normal','silver','gold','platinum')", name="ck_membership_tier"),
    )


__all__ = ["Contract", "Membership"]
