# alpha-crm-delivery

公开交付快照：会员空间平台（商务会员空间 CRM）数据层 —— SQLAlchemy 2 模型、Alembic 迁移、造数/清理/迁移核对脚本、pytest 验收用例。

- 技术栈：Python 3.12 / PostgreSQL 16 / SQLAlchemy 2 (async, psycopg3) / Alembic / pytest
- 统一约定：`id` UUID（`gen_random_uuid()`）、`org_id`、`site_id`、`created_at`、`created_by`、`updated_at`、`deleted_at`（软删除）；金额一律以「分」存整数；配置只从环境变量读取；不引入任何向境外发送数据的第三方 SDK；数据全部为虚构样例。

## 已覆盖的工单

| 工单 | 表/脚本 | 验收点 |
| --- | --- | --- |
| S2-CRM-001 企业/联系人/标签 | `companies` / `contacts` / `tags` / `company_tags` | CHECK、部分唯一索引、软删除复用 |
| S2-CRM-007 合同 | `crm_contract`（+ `crm_membership` 桩表） | upgrade/downgrade 往返、FK 增删、状态机 CHECK |
| S3-SALES-0xx 活动报名 | `event_signups` / `event_tickets` / `event_checkins` | 部分唯一索引、取消后可重报、签到唯一 |
| S2-CRM-004 互动记录 | `crm_interaction` | 时长 0–1440、纪要 1–5000 字 CHECK、DESC 索引、EXPLAIN |
| 迁移核对 | `scripts/reconcile_members.py` | 六类差异、退出码 0/1/2、手机号掩码 |
| E2E 造数清理 | `scripts/seed.py` / `cleanup.py` | 六场景、`external_key` 幂等、`E2E_ENV=prod` 零写请求 |

## 目录

```
app/        模型（models*.py）、引擎与会话、Windows 事件循环策略
alembic/    迁移环境与版本 0001–0006
scripts/    seed.py 六场景造数、cleanup.py 按 run_id 清理、normalize.py 归一、
            reconcile_members.py 迁移核对、make_fixtures.py 生成核对夹具
tests/      50 个用例：模型约束、造数幂等、清理范围、归一与掩码、迁移核对六类差异、
            契约域、活动域、互动记录域（含 EXPLAIN 断言）
```

## 快速开始

```bash
python -m venv .venv && . .venv/Scripts/activate        # Windows
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
export DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55432/alpha
alembic upgrade head
pytest -q
```

本地验证结果：`50 passed in 42.91s`；1000 家企业 + 5000 条联系人的迁移核对 0.69 秒（验收线 120 秒）。

## 互动记录（S2-CRM-004）验收证据

建表与约束：

- `type` IN (visit, call, wechat, meeting, event, email, other)；`source` IN (manual, import, system)，默认 `manual`
- `CHECK duration_minutes IS NULL OR 0 <= duration_minutes <= 1440`
- `CHECK char_length(summary) BETWEEN 1 AND 5000`
- 索引 `(org_id, company_id, occurred_at DESC)`、`(org_id, contact_id, occurred_at DESC)`、`(org_id, owner_user_id, occurred_at DESC)`；`summary` 的 GIN 三元组索引在有 `pg_trgm` 的库上创建，精简版 PG（无 contrib）自动跳过并在 `alembic check` 中排除比较

灌入 1 万条虚构互动后，「某企业最近 20 条」的 EXPLAIN（PostgreSQL 16.2 实测）：

```
Limit  (cost=0.29..2.22 rows=20 width=41)
  ->  Index Scan using ix_crm_interaction_company on crm_interaction  (cost=0.29..967.41 rows=10000 width=41)
        Index Cond: ((org_id = '11111111-1111-1111-1111-111111111111'::uuid)
                     AND (company_id = '577e78e1-2cec-47db-ac0e-f587443a75ad'::uuid))
```

父表映射：本快照的父表是 `companies` / `contacts`，在会员空间平台的完整模型里对应 `crm_company` / `crm_contact`；集成时只需在迁移里改 `ForeignKey` 目标，本表其余定义不变。`lead_id` / `opportunity_id` 按工单要求只建列，外键由线索表、商机表的迁移补建。

## 说明

- `0002_trgm` 与 `0006_crm_interaction` 的 GIN 索引在没有 `pg_trgm` 的 PostgreSQL 构建上会打印 `pg_trgm unavailable -> skipping ...` 并跳过，迁移链仍可完整跑到 head；`alembic check` 零漂移。
- `scripts/reconcile_members.py` 退出码：0 无差异 / 1 有差异 / 2 配置或输入错误；报告与差异明细写到 `out/reconcile/`，手机号只输出掩码。
- 仓库为公开交付快照，不含任何真实企业或个人信息，全部为虚构样例。
