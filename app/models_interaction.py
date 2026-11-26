"""crm_interaction — 工作人员与企业/联系人的每次接触记录。

工单 【S2-CRM-004】。公共字段沿用基座约定（id UUID / org_id / site_id /
created_at / created_by / updated_at / deleted_at 软删除）。金额字段本表没有。

父表说明：本基座的父表是 `companies`（企业）与 `contacts`（联系人），
在会员空间平台的完整模型里分别对应 `crm_company` / `crm_contact`；
若集成时父表名不同，只需在迁移里改 ForeignKey 目标，本表其余定义不变。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    desc,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import Timestamped, UUIDPk

INTERACTION_TYPES = ("visit", "call", "wechat", "meeting", "event", "email", "other")
INTERACTION_SOURCES = ("manual", "import", "system")

_TYPE_IN = "(" + ", ".join("'%s'" % t for t in INTERACTION_TYPES) + ")"
_SOURCE_IN = "(" + ", ".join("'%s'" % s for s in INTERACTION_SOURCES) + ")"


class Interaction(UUIDPk, Timestamped, Base):
    __tablename__ = "crm_interaction"

    org_id: Mapped[PGUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    site_id: Mapped[PGUUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True))

    company_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    contact_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    next_action: Mapped[str | None] = mapped_column(String(200))
    next_action_due: Mapped[date | None] = mapped_column(Date)
    lead_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True))
    opportunity_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True))
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'manual'")
    )
    owner_user_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True))
    merged_into_id: Mapped[PGUUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("crm_interaction.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("type IN " + _TYPE_IN, name="ck_crm_interaction_type"),
        CheckConstraint("source IN " + _SOURCE_IN, name="ck_crm_interaction_source"),
        CheckConstraint(
            "duration_minutes IS NULL OR (duration_minutes >= 0 AND duration_minutes <= 1440)",
            name="ck_crm_interaction_duration",
        ),
        CheckConstraint(
            "char_length(summary) >= 1 AND char_length(summary) <= 5000",
            name="ck_crm_interaction_summary_len",
        ),
        # AC3 依赖的三个查询索引（企业近 20 条 / 联系人近 20 条 / 记录人近 20 条）
        Index("ix_crm_interaction_company", "org_id", "company_id", desc("occurred_at")),
        Index("ix_crm_interaction_contact", "org_id", "contact_id", desc("occurred_at")),
        Index("ix_crm_interaction_owner", "org_id", "owner_user_id", desc("occurred_at")),
        # 关键字搜索用 GIN 三元组索引；生产库有 pg_trgm，本地 PG16.2（pgserver 精简版）
        # 没有 contrib，迁移与 alembic check 都会按可用性跳过（见 app/models.py 注释）
        Index(
            "ix_crm_interaction_summary_trgm",
            "summary",
            postgresql_using="gin",
            postgresql_ops={"summary": "gin_trgm_ops"},
        ),
    )
