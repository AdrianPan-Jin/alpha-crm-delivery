"""contract table, e-sign state and the membership link

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-26

Creates ``crm_contract``.  The link from ``crm_membership`` is added in
``0004`` as well, but only when that table exists: the buyer's project owns
the full membership table, so the migration must stay usable both in this
standalone snapshot (creates a minimal stub first) and in a database where
``crm_membership`` is already present (adds the FK only).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_contract",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contract_no", sa.String(32), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("party_a_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("party_b_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sign_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("esign_status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("amount_cents", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_contract_company", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('draft','active','terminated')", name="ck_contract_status"),
        sa.CheckConstraint("esign_status IN ('pending','signed','void')", name="ck_contract_esign_status"),
        sa.CheckConstraint(
            "NOT (status = 'active' AND esign_status <> 'signed')",
            name="ck_contract_active_requires_signed",
        ),
        sa.CheckConstraint("amount_cents >= 0", name="ck_contract_amount_nonneg"),
        sa.CheckConstraint("length(btrim(contract_no)) > 0", name="ck_contract_no_nonempty"),
    )
    op.create_index("ix_contacts_site_id", "contacts", ["site_id"])
    op.create_index("ix_tags_site_id", "tags", ["site_id"])
    op.create_index("ix_crm_contract_org_id", "crm_contract", ["org_id"])
    op.create_index("ix_crm_contract_site_id", "crm_contract", ["site_id"])
    op.create_index("ix_crm_contract_company_id", "crm_contract", ["company_id"])
    op.create_index("ix_contract_company_status", "crm_contract", ["company_id", "status"])
    op.create_index(
        "uq_contract_org_no_alive",
        "crm_contract",
        ["org_id", "contract_no"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # The membership table belongs to the project; create a minimal stub only
    # when it is absent so this snapshot stays runnable from an empty database.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('crm_membership') IS NULL THEN
                CREATE TABLE crm_membership (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    org_id uuid NOT NULL,
                    site_id uuid,
                    member_no varchar(32) NOT NULL,
                    tier varchar(16) NOT NULL DEFAULT 'normal',
                    starts_on timestamptz,
                    ends_on timestamptz,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    created_by uuid,
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    deleted_at timestamptz
                );
                CREATE INDEX ix_crm_membership_org_id ON crm_membership (org_id);
                CREATE INDEX ix_crm_membership_site_id ON crm_membership (site_id);
                CREATE UNIQUE INDEX uq_membership_org_no_alive
                    ON crm_membership (org_id, member_no) WHERE deleted_at IS NULL;
                ALTER TABLE crm_membership ADD CONSTRAINT ck_membership_tier
                    CHECK (tier IN ('normal','silver','gold','platinum'));
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE crm_membership
            ADD COLUMN IF NOT EXISTS contract_id uuid;
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_membership_contract'
            ) THEN
                ALTER TABLE crm_membership
                    ADD CONSTRAINT fk_membership_contract
                    FOREIGN KEY (contract_id) REFERENCES crm_contract (id) ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_crm_membership_contract_id ON crm_membership (contract_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_crm_membership_contract_id")
    op.execute("ALTER TABLE crm_membership DROP CONSTRAINT IF EXISTS fk_membership_contract")
    op.execute("ALTER TABLE crm_membership DROP COLUMN IF EXISTS contract_id")
    op.drop_index("uq_contract_org_no_alive", table_name="crm_contract")
    op.drop_index("ix_contract_company_status", table_name="crm_contract")
    op.drop_index("ix_crm_contract_company_id", table_name="crm_contract")
    op.drop_index("ix_crm_contract_site_id", table_name="crm_contract")
    op.drop_index("ix_crm_contract_org_id", table_name="crm_contract")
    op.drop_index("ix_tags_site_id", table_name="tags")
    op.drop_index("ix_contacts_site_id", table_name="contacts")
    op.drop_table("crm_contract")
