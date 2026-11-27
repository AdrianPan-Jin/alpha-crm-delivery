"""crm_interaction — 互动记录表模型与迁移

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26

工单 【S2-CRM-004】：
- 统一公共字段 + company_id / contact_id / type / occurred_at / duration_minutes /
  summary / next_action / next_action_due / lead_id / opportunity_id / source /
  owner_user_id / merged_into_id
- CHECK duration_minutes BETWEEN 0 AND 1440
- CHECK char_length(summary) BETWEEN 1 AND 5000
- 索引 (org_id, company_id, occurred_at DESC) 等三条
- summary 的 GIN 三元组索引：pg_trgm 不可用时跳过（本地 pgserver 精简版无 contrib）
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _has_trgm(conn) -> bool:
    return conn.exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm'"
    ).scalar() is not None


def upgrade() -> None:
    op.create_table(
        "crm_interaction",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("next_action", sa.String(200), nullable=True),
        sa.Column("next_action_due", sa.Date(), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(20), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "merged_into_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_interaction.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "type IN ('visit','call','wechat','meeting','event','email','other')",
            name="ck_crm_interaction_type",
        ),
        sa.CheckConstraint(
            "source IN ('manual','import','system')",
            name="ck_crm_interaction_source",
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR (duration_minutes >= 0 AND duration_minutes <= 1440)",
            name="ck_crm_interaction_duration",
        ),
        sa.CheckConstraint(
            "char_length(summary) >= 1 AND char_length(summary) <= 5000",
            name="ck_crm_interaction_summary_len",
        ),
    )

    # 三个「最近 20 条」查询索引，按需求显式 DESC
    op.execute(
        "CREATE INDEX ix_crm_interaction_company "
        "ON crm_interaction (org_id, company_id, occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_crm_interaction_contact "
        "ON crm_interaction (org_id, contact_id, occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_crm_interaction_owner "
        "ON crm_interaction (org_id, owner_user_id, occurred_at DESC)"
    )

    if _has_trgm(op.get_bind()):
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX ix_crm_interaction_summary_trgm "
            "ON crm_interaction USING gin (summary gin_trgm_ops)"
        )
    else:
        print("pg_trgm unavailable -> skipping ix_crm_interaction_summary_trgm")


def downgrade() -> None:
    if _has_trgm(op.get_bind()):
        op.execute("DROP INDEX IF EXISTS ix_crm_interaction_summary_trgm")
    op.execute("DROP INDEX IF EXISTS ix_crm_interaction_owner")
    op.execute("DROP INDEX IF EXISTS ix_crm_interaction_contact")
    op.execute("DROP INDEX IF EXISTS ix_crm_interaction_company")
    op.drop_table("crm_interaction")
