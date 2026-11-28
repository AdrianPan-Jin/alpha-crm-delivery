"""0002 — 已发布版本有效期互斥（AC2）

PostgreSQL 排他约束：同一 org + 同一规则下，status='published' 且未软删的版本，
其 [valid_from, valid_to) 日期区间不得重叠。依赖 btree_gist 扩展（无 contrib 环境自动跳过）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CONSTRAINT = "ex_quote_version_published_overlap"


def _has_btree_gist(bind) -> bool:
    return bind.exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'btree_gist'"
    ).scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_btree_gist(bind):
        print("[0002] btree_gist unavailable -> skipping exclusion constraint")
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE quote_rule_version
        ADD CONSTRAINT {CONSTRAINT}
        EXCLUDE USING gist (
            org_id WITH =,
            rule_id WITH =,
            daterange(valid_from, valid_to, '[)') WITH &&
        )
        WHERE (deleted_at IS NULL AND status = 'published')
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_btree_gist(bind):
        return
    op.execute(f"ALTER TABLE quote_rule_version DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    # 不 drop btree_gist：其它模块可能复用
