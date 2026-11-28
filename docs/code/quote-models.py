"""报价规则域模型（对应 S5-DOC-029）。

三张表：
  quote_rule          规则主体（org 作用域）
  quote_rule_version  版本，有效期区间 [valid_from, valid_to)，published 版本互斥
  quote_rule_item     规则条目，一条规则 12 项

平台统一约定：UUID 主键、org_id/site_id 作用域、created_at/created_by/updated_at/deleted_at
软删除、金额用整数分、配置只从环境变量读取。
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuoteRule(UUIDPk, Timestamped, Base):
    __tablename__ = "quote_rule"

    org_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="CNY")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    remark: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("status IN ('draft','published','archived')", name="ck_quote_rule_status"),
        CheckConstraint("currency IN ('CNY','USD','HKD')", name="ck_quote_rule_currency"),
        Index("uq_quote_rule_org_code_alive", "org_id", "code", unique=True,
              postgresql_where=Text("deleted_at IS NULL")),
        Index("ix_quote_rule_deleted_at", "deleted_at"),
    )


class QuoteRuleVersion(UUIDPk, Timestamped, Base):
    """版本有效期 [valid_from, valid_to)；None 表示无限期。

    已发布版本之间不允许重叠（数据库排他约束，见迁移 0002）。
    """
    __tablename__ = "quote_rule_version"

    org_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quote_rule.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("status IN ('draft','published','archived')", name="ck_quote_version_status"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_quote_version_range"),
        Index("uq_quote_version_rule_no", "rule_id", "version_no", unique=True),
        Index("ix_quote_version_rule_id", "rule_id"),
        Index("ix_quote_version_deleted_at", "deleted_at"),
    )


class QuoteRuleItem(UUIDPk, Timestamped, Base):
    """一条规则条目；member_company_id 与 prospect_name 二者恰好一个非空。"""
    __tablename__ = "quote_rule_item"

    org_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quote_rule_version.id", ondelete="CASCADE"), nullable=False
    )
    member_company_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    prospect_name: Mapped[str | None] = mapped_column(String(120))
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    discount_bp: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        # AC3：成员企业与潜在客户名，二选一
        CheckConstraint("(member_company_id IS NULL) <> (prospect_name IS NULL)",
                        name="ck_quote_item_exactly_one_subject"),
        CheckConstraint("unit_price_cents >= 0", name="ck_quote_item_price_nonneg"),
        CheckConstraint("min_qty >= 1", name="ck_quote_item_min_qty"),
        CheckConstraint("discount_bp BETWEEN 0 AND 10000", name="ck_quote_item_discount"),
        Index("uq_quote_item_version_seq", "version_id", "seq_no", unique=True),
        Index("ix_quote_item_version_id", "version_id"),
        Index("ix_quote_item_deleted_at", "deleted_at"),
    )
