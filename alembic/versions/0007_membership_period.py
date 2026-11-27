"""crm_membership — 会员期间重叠互斥（S2-CRM-003）

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-27

工单 2762 要求：
- 会员表含档位、起止日期；
- 同一企业同一时刻只允许一条有效会员：两条 active 且日期区间重叠 → 拒绝；
- 上一条改为 terminated 或软删除后，重叠区间可以再插入；
- end_date < start_date 被 CHECK 拒绝；
- upgrade/downgrade 往返成功，alembic check 零漂移（EXCLUDE 不被重复生成）。

实现要点：
* EXCLUDE 约束需要 ``btree_gist`` 扩展；本地 pgserver 精简版没有 contrib 时会跳过，
  迁移仍然可跑（README 里写明这条降级路径）。
* 约束带 ``WHERE deleted_at IS NULL AND status <> 'terminated'``，
  这样「软删 / 已终止」的历史会员不会阻塞新会员。
* 区间用 ``daterange(start_date, end_date, '[]')``（闭区间：到期当天仍有效）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

EXCLUDE_NAME = "ex_membership_period_overlap"


def _has_btree_gist(conn) -> bool:
    return conn.exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'btree_gist'"
    ).first() is not None


def upgrade() -> None:
    conn = op.get_bind()
    has_gist = _has_btree_gist(conn)
    if has_gist:
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # columns (idempotent: the stub in 0004 may already be present)
    op.execute(
        """
        ALTER TABLE crm_membership
            ADD COLUMN IF NOT EXISTS company_id uuid,
            ADD COLUMN IF NOT EXISTS status varchar(16) NOT NULL DEFAULT 'active',
            ADD COLUMN IF NOT EXISTS start_date date,
            ADD COLUMN IF NOT EXISTS end_date date;
        """
    )
    # backfill date period from the timestamp columns when possible
    op.execute(
        """
        UPDATE crm_membership
           SET start_date = COALESCE(start_date, starts_on::date),
               end_date   = COALESCE(end_date, ends_on::date)
         WHERE (start_date IS NULL AND starts_on IS NOT NULL)
            OR (end_date IS NULL AND ends_on IS NOT NULL);
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_membership_status') THEN
                ALTER TABLE crm_membership ADD CONSTRAINT ck_membership_status
                    CHECK (status IN ('active','suspended','terminated','expired'));
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_membership_dates') THEN
                ALTER TABLE crm_membership ADD CONSTRAINT ck_membership_dates
                    CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date);
            END IF;
        END
        $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_crm_membership_company ON crm_membership (company_id, status)")

    if has_gist:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{EXCLUDE_NAME}') THEN
                    ALTER TABLE crm_membership
                        ADD CONSTRAINT {EXCLUDE_NAME}
                        EXCLUDE USING gist (
                            org_id WITH =,
                            company_id WITH =,
                            daterange(start_date, end_date, '[]') WITH &&
                        ) WHERE (deleted_at IS NULL AND status <> 'terminated');
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    has_gist = _has_btree_gist(conn)
    if has_gist:
        op.execute(f"ALTER TABLE crm_membership DROP CONSTRAINT IF EXISTS {EXCLUDE_NAME}")
    op.execute("DROP INDEX IF EXISTS ix_crm_membership_company")
    op.execute("ALTER TABLE crm_membership DROP CONSTRAINT IF EXISTS ck_membership_status")
    op.execute("ALTER TABLE crm_membership DROP CONSTRAINT IF EXISTS ck_membership_dates")
    op.execute(
        """
        ALTER TABLE crm_membership
            DROP COLUMN IF EXISTS end_date,
            DROP COLUMN IF EXISTS start_date,
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS company_id;
        """
    )
