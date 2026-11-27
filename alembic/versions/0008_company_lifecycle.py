"""companies — 信用代码唯一、生命周期与健康分（S2-CRM-001）

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-27

工单 2761 要求：
- 同 org 内两条未删除企业使用同一统一社会信用代码（uscc）→ 唯一约束报错；
  软删一条后可再插入（部分唯一索引，WHERE deleted_at IS NULL）；
- health_score 写 101 或 -1 被 CHECK 拒绝；
- lifecycle_status 写枚举外的值被 CHECK 拒绝；
- name ILIKE '%example%' 命中 pg_trgm GIN 索引（EXPLAIN 贴 README）。

设计：
* 唯一性用部分唯一索引而不是表级 UNIQUE：软删除行不参与唯一性，
  与「同一信用代码可以换主体重新录入」的业务口径一致。
* health_score 允许 NULL（尚未评估），只约束取值区间。
* 索引 ix_companies_name_trgm 在 0002 里创建；无 pg_trgm 的构建自动跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE companies
            ADD COLUMN IF NOT EXISTS health_score smallint,
            ADD COLUMN IF NOT EXISTS lifecycle_status varchar(16) NOT NULL DEFAULT 'prospect';
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_companies_health_score') THEN
                ALTER TABLE companies ADD CONSTRAINT ck_companies_health_score
                    CHECK (health_score IS NULL OR health_score BETWEEN 0 AND 100);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_companies_lifecycle') THEN
                ALTER TABLE companies ADD CONSTRAINT ck_companies_lifecycle
                    CHECK (lifecycle_status IN ('prospect','active','at_risk','churned'));
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_org_uscc_alive
            ON companies (org_id, unified_credit_code)
            WHERE deleted_at IS NULL AND unified_credit_code IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_companies_org_uscc_alive")
    op.execute("ALTER TABLE companies DROP CONSTRAINT IF EXISTS ck_companies_lifecycle")
    op.execute("ALTER TABLE companies DROP CONSTRAINT IF EXISTS ck_companies_health_score")
    op.execute(
        """
        ALTER TABLE companies
            DROP COLUMN IF EXISTS lifecycle_status,
            DROP COLUMN IF EXISTS health_score;
        """
    )
