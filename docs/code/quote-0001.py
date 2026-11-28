"""0001 — 报价规则三表（quote_rule / quote_rule_version / quote_rule_item）"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')  # gen_random_uuid()

    op.create_table(
        "quote_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True)),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("remark", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('draft','published','archived')", name="ck_quote_rule_status"),
        sa.CheckConstraint("currency IN ('CNY','USD','HKD')", name="ck_quote_rule_currency"),
    )
    op.create_index("ix_quote_rule_deleted_at", "quote_rule", ["deleted_at"])
    op.execute(
        "CREATE UNIQUE INDEX uq_quote_rule_org_code_alive ON quote_rule (org_id, code) "
        "WHERE deleted_at IS NULL"
    )

    op.create_table(
        "quote_rule_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quote_rule.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('draft','published','archived')", name="ck_quote_version_status"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_quote_version_range"),
    )
    op.create_index("ix_quote_version_deleted_at", "quote_rule_version", ["deleted_at"])
    op.create_index("ix_quote_version_rule_id", "quote_rule_version", ["rule_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_quote_version_rule_no ON quote_rule_version (rule_id, version_no)"
    )

    op.create_table(
        "quote_rule_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("quote_rule_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_company_id", postgresql.UUID(as_uuid=True)),
        sa.Column("prospect_name", sa.String(120)),
        sa.Column("seq_no", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(120), nullable=False),
        sa.Column("unit_price_cents", sa.BigInteger(), nullable=False),
        sa.Column("min_qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("discount_bp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("(member_company_id IS NULL) <> (prospect_name IS NULL)",
                           name="ck_quote_item_exactly_one_subject"),
        sa.CheckConstraint("unit_price_cents >= 0", name="ck_quote_item_price_nonneg"),
        sa.CheckConstraint("min_qty >= 1", name="ck_quote_item_min_qty"),
        sa.CheckConstraint("discount_bp BETWEEN 0 AND 10000", name="ck_quote_item_discount"),
    )
    op.create_index("ix_quote_item_deleted_at", "quote_rule_item", ["deleted_at"])
    op.create_index("ix_quote_item_version_id", "quote_rule_item", ["version_id"])
    op.execute("CREATE UNIQUE INDEX uq_quote_item_version_seq ON quote_rule_item (version_id, seq_no)")


def downgrade() -> None:
    op.drop_table("quote_rule_item")
    op.drop_table("quote_rule_version")
    op.drop_table("quote_rule")
    # 不 drop pgcrypto：其它模块可能复用
