"""Multi-tenant membership-domain models (companies / contacts / tags).

Deliberately conservative: UUID pk, org/site scoping, soft delete, CHECK
constraints for enumerated columns, partial unique indexes that ignore soft
deleted rows, money in cents.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class Tenant:
    org_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Company(Base, UUIDPk, Tenant, Timestamped):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unified_credit_code: Mapped[str | None] = mapped_column(String(18), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(16), nullable=False, server_default="normal")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    external_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("level in ('normal','silver','gold','platinum')", name="ck_companies_level"),
        CheckConstraint("status in ('active','inactive','frozen')", name="ck_companies_status"),
        CheckConstraint("revenue_cents >= 0", name="ck_companies_revenue_nonneg"),
        UniqueConstraint("org_id", "external_key", name="uq_companies_org_external_key"),
        Index(
            "uq_companies_org_name_alive",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at is null"),
        ),
    )


class Contact(Base, UUIDPk, Tenant, Timestamped):
    __tablename__ = "contacts"

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(11), nullable=False)
    title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        CheckConstraint("phone ~ '^1[3-9][0-9]{9}$'", name="ck_contacts_phone"),
        Index(
            "uq_contacts_org_phone_alive",
            "org_id",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at is null"),
        ),
    )


class Tag(Base, UUIDPk, Tenant, Timestamped):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(32), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_tags_org_name"),)


class CompanyTag(Base, Timestamped):
    __tablename__ = "company_tags"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
