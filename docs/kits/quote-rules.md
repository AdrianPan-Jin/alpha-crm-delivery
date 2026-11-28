# 报价规则域（S5-DOC-029）交付件

PostgreSQL 3 表 + Alembic 迁移 + 幂等种子 + 9 个测试，对应工单 1964「报价规则表与数据模型迁移」。

## 结构

```
app/models.py            三表模型（quote_rule / quote_rule_version / quote_rule_item）
app/db.py                async engine、session、Base
alembic/versions/0001_quote_rules.py   建表 + 索引 + CHECK
alembic/versions/0002_version_overlap.py  published 版本有效期互斥（btree_gist EXCLUDE）
scripts/seed_quote_rules.py            幂等种子：1 规则 + 1 已发布版本 + 12 条目
tests/                   迁移往返/check、二选一约束、重叠互斥、种子幂等
```

## 逐条 AC 对照

| AC | 落点 | 验证 |
| --- | --- | --- |
| ① 迁移可往返，`alembic check` 零漂移 | `alembic/versions/0001`、`0002` | `tests/test_migration.py::test_upgrade_downgrade_roundtrip_and_check` |
| ② 已发布版本有效期重叠被数据库拒绝 | 0002 的 `EXCLUDE USING gist (... daterange(valid_from, valid_to, '[)') WITH &&) WHERE (deleted_at IS NULL AND status='published')` | `tests/test_quote_rules.py`（ExclusionViolation / 相邻允许 / draft 与软删不参与） |
| ③ `member_company_id` 与 `prospect_name` 二选一 | `ck_quote_item_exactly_one_subject`：`(member_company_id IS NULL) <> (prospect_name IS NULL)` | `tests/test_quote_item_subject.py`（两空/两值拒绝，各一方通过） |
| ④ 种子导入后 `quote_rule_item` 恰 12 行 | `scripts/seed_quote_rules.py`（`ON CONFLICT (version_id, seq_no) DO UPDATE`） | `tests/test_seed.py`（首次 12 行、重复导入仍 12 行） |

## 平台统一约定

- UUID 主键（`gen_random_uuid()`）、`org_id` / `site_id` 作用域
- `created_at` / `created_by` / `updated_at` / `deleted_at` 软删除
- 金额整数分（`unit_price_cents BIGINT`）、折扣基点（`discount_bp 0–10000`）
- 配置只从环境变量读（`DATABASE_URL`），不引入向境外发送数据的 SDK
- 部分唯一索引带 `WHERE deleted_at IS NULL`，软删后可复用同一 code

## 跑起来

```bash
python -m pytest -q                     # 9 passed
PG_PORT=55433 python -m pytest -q       # 有 btree_gist 的实例上跑互斥用例
DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55432/qr_demo \
  python -m alembic upgrade head
DATABASE_URL=... python scripts/seed_quote_rules.py   # 打印 items=12
```

## 已知边界

- 无 `btree_gist` 的环境（本机 PG16.2 的 pgserver 版）会自动跳过互斥约束并打印提示；PG19 完整版实测生效。
- 种子里的价格是虚构样例；真实价目由业务方维护。
