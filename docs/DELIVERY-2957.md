# S4-GO-029 会员主数据迁移核对脚本 — 交付说明（2957）

> 交付物在仓库 `project-alpha/deliverables/_s2`，公开镜像 <https://github.com/AdrianPan-Jin/alpha-crm-delivery>；
> 本机实测环境：Windows + PostgreSQL 16.2（无 contrib）与 PostgreSQL 19.0（含 pg_trgm / btree_gist）双实例、Python 3.12、psycopg 3。

## 1. 交付清单

| 文件 | 作用 |
| --- | --- |
| `scripts/reconcile_members.py` | 核对主程序：五类对象逐字段比对、六类差异分类、退出码、CSV/报告输出 |
| `scripts/normalize.py` | 三条归一化规则（空白折叠 / 全角转半角 / 国家码剥离）与手机号掩码 |
| `scripts/make_fixtures.py` | 虚构数据生成（clean / dirty 两套，dirty 人工植入六类差异） |
| `scripts/common.py` | 配置、`E2E_ENV=prod` 拒绝执行、manifest 写出 |
| `alembic/versions/0001–0006` | 被核对目标库的表结构与迁移 |
| `tests/test_reconcile.py` | 核对逻辑单测（clean 0 差异、dirty 六类齐全、缺列 exit 2、性能 1000/5000 < 120s） |
| `tests/test_normalize.py` | 归一化 12 个参数化用例 |
| `README.md` / `docs/*` | 命令、口径、验收证据 |

## 2. 逐条 AC 对照（附实测数字）

**AC1 六类已知差异全部检出**
`make_fixtures.py --load-target` 造 clean 后叠加 dirty 变更集，实测输出：

```
$ python -m scripts.reconcile_members --source fixtures/dirty
{"differences": 10, "by_kind": {"credit_code_dup": 1, "duplicate": 1, "many_to_one": 1,
 "mismatch": 4, "missing": 2, "orphan": 1}, "elapsed_s": 0.059}
```

六类（missing / duplicate / many_to_one / mismatch / orphan / credit_code_dup）全部命中；
`many_to_one` 由 `legacy_map` 里「C900 与 C001 指向同一个目标 uuid」构造，能识别旧系统重复映射导致的多对一。

**AC2 零差异 exit 0、有差异非零**
clean 数据集：`{"differences": 0, "by_kind": {}, "elapsed_s": 0.083}` → `exit 0`；
dirty 数据集 → `exit 1`；输入/配置错误 → `exit 2`。三条都有单测（`tests/test_reconcile.py`）。

**AC3 明细 CSV 手机号全部掩码**
输出 `out/reconcile/diffs.csv`（UTF-8 BOM，Excel 直开），手机号列形如 `137****7003`；
写出前对整表再扫一遍 11 位手机号，命中即视为程序缺陷并以 `exit 2` 退出（自检而不是靠人工抽查）。

**AC4 三条归一化规则各有用例**
`tests/test_normalize.py` 覆盖：`" 张 三 "` → `张三`、`ＡＢＣ１２３` → `ABC123`、`+86 138-0013-8000` → `13800138000`，另含 `0086` 前缀、`86` 前缀、混合横线与空格等边界。

**AC5 1000 企业 / 5000 联系人 < 2 分钟**
单测 `test_performance_budget` 实测 **0.69 s**（同一进程内建表、灌数、核对、断言），日志见 `out/reconcile/report.md` 的 `elapsed_s` 字段。

## 3. 复现步骤

```bash
python -m scripts.make_fixtures --out fixtures --load-target   # 造 clean 并灌目标库
python -m scripts.make_fixtures --dirty --out fixtures/dirty   # 造 dirty 变更集
python -m scripts.reconcile_members --source fixtures/clean   # exit 0
python -m scripts.reconcile_members --source fixtures/dirty   # exit 1, 六类差异
pytest tests/test_reconcile.py tests/test_normalize.py -q
```

## 4. 边界与假设

- 目标库连接由 `DATABASE_URL` 给出（默认 `postgresql+psycopg://postgres@127.0.0.1:55432/alpha`），不做任何写操作，全部只读事务。
- 字段口径按平台统一约定：UUID 主键、`org_id`、`site_id`、软删除 `deleted_at`、金额以分存整数。
- 源系统导出格式不在本脚本内硬编码：通过 `fixtures/*.json`（或 CSV）适配层接入，客户提供真实导出后只需改适配层。
- 性能数字来自 SQLite 之外的本地 PostgreSQL；若目标库网络延迟高，脚本按 500 行批量游标读取，实测仍远低于 2 分钟上限。
