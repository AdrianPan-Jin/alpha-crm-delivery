# DELIVERY: CRM 会员空间平台交付基座（S2 系列）

本仓库是围绕「会员空间平台」系列工单（企业/联系人/标签数据模型、测试环境灌数与清理、主数据迁移核对、财务导出）构建的可复用交付基座。代码以 PostgreSQL + Python 为准，SQLAlchemy 2.0 async + psycopg3 + Alembic，测试用 pytest。

## 目录

```
app/            # 运行时代码
  db.py         # async engine / session 依赖 / Base
  models.py     # Company / Contact / Tag / CompanyTag，含 CHECK 与部分唯一索引
  eventloop.py  # Windows 下 SelectorEventLoop 策略
alembic/        # 迁移：0001 初始表、0002 pg_trgm GIN 索引（无 contrib 时自动降级 no-op）、0003 legacy_map
scripts/        # 工具脚本
  common.py     # 环境变量、E2E_ENV=prod 保护、manifest
  seed.py       # 六场景灌数（empty/single/bulk/duplicate/soft-deleted/mixed/all）
  cleanup.py    # 按 run_id 软删 + 硬删
  normalize.py  # 全角/空白/手机号/统一社会信用代码归一
  reconcile_members.py  # 五类对象 × 六类差异的迁移核对，退出码 0/1/2
  make_fixtures.py      # 生成 clean / dirty 夹具
tests/          # pytest（模型、seed+cleanup、normalize、reconcile、性能）
```

## 关键设计

1. **多租户隔离**：所有业务表带 `org_id`（+ 可选 `site_id`），唯一约束与部分唯一索引均以 `org_id` 为前缀。
2. **软删除**：`deleted_at` 为空才参与唯一性（部分唯一索引 `WHERE deleted_at IS NULL`），保证软删后可重建同名数据。
3. **幂等灌数**：公司以 `(org_id, external_key)` 冲突更新；联系人以 `(org_id, phone) WHERE deleted_at IS NULL` 冲突更新。
4. **差异检出**：`missing / duplicate / many_to_one / mismatch / orphan / credit_code_dup` 六类；`legacy_map` 复合主键 `(org_id, entity, source_id, target_id)` 支持一对多与多对一。
5. **数据安全**：所有输出（CSV/Markdown）中手机号只保留掩码 `138****8000`，输出前再扫一遍 11 位手机号，命中直接以退出码 2 失败。
6. **生产保护**：`E2E_ENV=prod` 时灌数/清理脚本不发起任何请求、以非零码退出。

## 验收自测

```bash
pip install -r requirements.txt   # 建议用镜像源
alembic upgrade head
python scripts/make_fixtures.py --out fixtures
python scripts/make_fixtures.py --out fixtures --load-target   # 灌 clean 到目标库
python scripts/reconcile_members.py --source fixtures/clean --out out/reconcile    # 期望 0 差异，退出码 0
python scripts/reconcile_members.py --source fixtures/dirty --out out/reconcile    # 期望 6 类差异，退出码 1
pytest -q
```

实测（PostgreSQL 16.2）：干净集 0 差异退出 0；脏集 11 处差异退出 1；31 个测试全绿；1000 企业 + 5000 联系人核对 0.69s（验收线 120s）。

## 平台统一约定

- 主键 UUID（`gen_random_uuid()`），字段 `org_id`、`site_id`、`created_at`、`created_by`、`updated_at`、`deleted_at`。
- 金额以「分」存整数（`BigInteger`）。
- 配置只从环境变量读取，不硬编码。
- 不引入会向境外发送数据的第三方 SDK。
