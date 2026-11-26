"""legacy id mapping used by the migration reconciliation

One row per (org, entity, source_id, target_id) so the table is able to represent
both anomalies the reconciliation must report: a source id mapped twice to
different uuids (duplicate) and several source ids mapped to one uuid (many-to-one).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_map",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("org_id", "entity", "source_id", "target_id"),
    )
    op.create_index("ix_legacy_map_target", "legacy_map", ["target_id"])


def downgrade() -> None:
    op.drop_table("legacy_map")
