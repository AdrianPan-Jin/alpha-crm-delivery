# _s2 — 会员空间平台交付基座（可复用）

针对 ClawHunt 上「会员空间平台（Member Space Platform）」系列工单搭的可复用基座：
企业/联系人/标签、合同与会员期间、活动报名、互动记录、播客归因。
同一套迁移与测试在 **PostgreSQL 19（带 contrib）** 与 **PostgreSQL 16.2（无 contrib）** 上都跑过，
`alembic check` 零漂移。

```
tests/  PostgreSQL 19：73 passed（含播客归因 9 个）
        PostgreSQL 16.2：65 passed + 8 skipped（btree_gist / pg_trgm 用例自动跳过并打印原因）
```

## 快速开始

```bash
python -m venv .venv && . .venv/Scripts/activate     # Windows
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

export DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:55433/alpha"
alembic upgrade head
pytest -q
```

两个实例都用环境变量切换：`PG_HOST` / `PG_PORT`（默认 `127.0.0.1:55432`）。
PostgreSQL 16.2 是精简构建、没有 contrib，`0002`/`0006`/`0007` 里的 GIN / EXCLUDE 会自动降级或跳过。

## 目录

- `app/db.py` — engine 工厂、Session 依赖、`Base`
- `app/models.py` — companies / contacts / tags / company_tags / Company（health_score、lifecycle_status、uscc 部分唯一索引）
- `app/models_contract.py` — Contract（合同号部分唯一、签署状态、金额分）+ Membership（会员期间）
- `app/models_event.py` — EventSignup / EventTicket / EventCheckin
- `app/models_interaction.py` — Interaction（crm_interaction 互动记录）
- `app/models_legacy.py` — LegacyMap（迁移核对用的旧系统 ID 映射）
- `app/podcast/` — 播客归因：`models.py` / `stubs.py` / `attribution.py` / `daily.py`
- `alembic/versions/0001…0009` — 建表、pg_trgm、legacy_map、合同、活动、互动、会员期间、企业生命周期、播客归因
- `scripts/` — seed / cleanup / normalize / reconcile_members / make_fixtures
- `docs/metrics-podcast-attribution.md` — 播客归因口径（与收听汇总同册）
- `tests/` — 约束、幂等、归零、核对、期间互斥、企业字段、播客归因

## 平台统一约定（已内置）

1. 主键 UUID，`gen_random_uuid()` 生成
2. 所有业务表带 `org_id`（必填）与可选 `site_id`
3. 删除为软删除（`deleted_at`），部分唯一索引天然忽略已删行
4. 金额一律整数分（`BigInteger`），不出现 float
5. 枚举列用 `varchar + CHECK`，不用 PG enum 类型（避免迁移锁）
6. 配置/密钥只从环境变量读；不引入会向境外发送数据的 SDK

## 播客归因（S6-POD-041）

```bash
# 单日增量（收听汇总之后跑）
python -m app.podcast.daily --date 2026-11-20
# 回填区间（含首尾），整日覆盖、可重复执行
python -m app.podcast.daily --backfill 2026-11-01:2026-11-20
```

规则摘要（完整口径见 `docs/metrics-podcast-attribution.md`）：

- 直接归因：当日创建 / 当日审批 / 当日接受的引荐请求，分别进 `intro_requests`、`intro_staff_approved`、`intro_accepted`
- 辅助归因：点击后 **0 ≤ C − T ≤ 24h** 的转化；同一用户同一对象按**最近一次点击**归属；并列时按 `episode_id` 升序
- 关闭个性化推荐的用户：计入总量，不写个体明细（`episode_conversion_events` 里不会出现该用户）
- 幂等：同一 `(org_id, stat_date)` 整日覆盖；回填与增量结果一致

### 与其他模块的集成点（当前为接口桩）

| 桩 | 方法 | 生产接线 |
| --- | --- | --- |
| `ConversionSource` | `conversions(start, end) -> Iterable[Conversion(kind, target_id, user_id, occurred_at)]` | 调活动报名 / 课程报名 / 公开机会对接三张表的只读接口 |
| `PreferenceSource` | `personalization_enabled(user_id) -> bool` | 调用户偏好服务 |

测试里用 `StaticConversionSource` / `StaticPreferenceSource` 注入固定数据，
生产环境替换为 HTTP 客户端即可，`compute_day()` 的签名不变。

## 验收证据（本仓库可直接复跑）

- 企业名模糊搜索（S2-CRM-001）：20 万行数据上 `EXPLAIN ANALYZE ... WHERE name ILIKE '%acme%'`
  → `Bitmap Index Scan on ix_companies_name_trgm`，Execution 3.05 ms（无索引时 `Seq Scan` + `Rows Removed by Filter: 19900`）。
  单测版本在 10 万行上断言同一索引被选中（小表 seq scan 是计划器正常行为，测试注释里已说明）。
- 迁移核对（S4-GO-029）：clean 数据 0 差异、exit 0；dirty 数据 10 处差异、exit 1，
  六类（missing/duplicate/many_to_one/mismatch/orphan/credit_code_dup）全覆盖，手机号掩码 `137****7003`。
- 会员期间互斥（S2-CRM-003）：重叠 `ExclusionViolation`、相邻放行、`terminated`/软删后可插、`end_date < start_date` 被 CHECK 拒绝。
- 播客归因（S6-POD-041）：23h/24h 计入、25h 不计；两次点击归最近一次；关闭个性化的用户只进总量；
  回填与增量一致（`tests/test_podcast_attribution.py`）。

## 本地验证记录

- PostgreSQL 19.0（`127.0.0.1:55433`，带 contrib）：`73 passed in 66.83s`，`alembic check` 无新操作
- PostgreSQL 16.2（`127.0.0.1:55432`，无 contrib）：`65 passed, 8 skipped in 81.94s`
- 灌数/清理 1000 企业 + 5000 联系人：迁移核对 0.69 秒（验收线 120 秒）
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
