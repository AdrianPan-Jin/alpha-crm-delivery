"""pg_trgm extension + trigram GIN index for company name search

Requires the pg_trgm contrib extension. On builds without contrib this revision
cannot run; keep the project on 0001 or install a full PostgreSQL distribution.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some binary distributions ship without contrib; keep the migration chain
    # usable there and simply skip the trigram index (documented in README).
    availability = op.get_bind().execute(
        sa.text("select count(*) from pg_available_extensions where name = 'pg_trgm'")
    ).scalar_one()
    if not availability:
        print("pg_trgm unavailable -> skipping trigram index (0002 no-op on this build)")
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_name_trgm ON companies USING gin (name gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_companies_name_trgm")
