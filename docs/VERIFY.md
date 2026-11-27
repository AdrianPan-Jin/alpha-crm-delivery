# 交付物可复现性验证（VERIFY）

本文件证明：**买方可以从零重建我们测试过的那棵树，并跑出同样的结果。**

## 为什么需要它

公开仓库 `alpha-crm-delivery` 里只有部分文件（网页写通道不稳定，0006–0009 迁移与多数测试是以纯文本快照发布的）。「快照 + 仓库 = 完整交付物，且测试全绿」这句话必须可验证，否则只是一个说法。

## 重建方式

```bash
python verify_bundle.py --out C:/tmp/verify        # 需要本机 PG19 在 127.0.0.1:55433
```

脚本做四件事：

1. 下载仓库 tarball（`codeload.github.com`；不可达时自动回退到 tree API + `raw.githubusercontent.com` 逐文件取）；
2. 下载 6 份纯文本快照（`paste.rs/V0RpF`、`/XJaTd`、`/3PX91`、`/srMfX`、`/8iv57`、`/rLfjW`），按 `===== FILE: <path> =====` 分隔还原成文件树，覆盖到仓库目录上；
3. 用 `PG_HOST` / `PG_PORT` 指向本地 PostgreSQL 19（含 pg_trgm、btree_gist），**不设置** `DATABASE_URL`（各测试自己建一次性库）；
4. 跑 `pytest -q`，输出 JSON 摘要并以退出码表示成败。

## 实测结果（2026-11-27 02:18）

```json
{
  "repo_files": 26,
  "snapshot_files_written": 50,
  "pytest_rc": 0,
  "pytest_tail": ["....", "91 passed in 84.76s (0:01:24)"]
}
```

即：仓库 26 个文件 + 快照 50 个文件 = 76 个文件，**91 项测试全绿，耗时 84.76 秒**（其中性能用例 0.69 秒，远低于验收线 120 秒）。

## 快照与仓库的差异

| 只在快照里 | 说明 |
| --- | --- |
| `alembic/env.py` | **覆盖仓库旧版**：仓库里那份缺 `include_object`（无 contrib 时排除 trgm 索引漂移）与 `await connection.commit()`（SQLAlchemy 2.x 隐式事务回滚导致 upgrade 不落库）；快照版是修复后的版本 |
| `alembic/versions/0006–0009` | 互动记录、会员期间互斥、企业生命周期、播客归因四个迁移 |
| `app/consistency/*`、`app/podcast/*` | 每日一致性自检引擎与播客归因域 |
| `tests/test_*`（8 个） | 契约、活动、互动、会员期间、企业、播客、一致性、seed/cleanup、normalize、reconcile |
| `docs/DELIVERY-2957.md`、`alembic.ini` | 交付说明与迁移配置 |

> 注意：快照是 **24 小时有效** 的纯文本托管，过期后按同一脚本重新生成（`project-alpha/ops/pub/full_*.md` 已在仓库侧的生成流程里）并替换 URL；长期方案是把这些文件直接推进仓库（网页写通道不稳，仍在重试）。

## 2026-11-27 02:50 复核（filebin 通道）

paste.rs 只有 ~24h 有效期，不适合「中标后数天才被 review」的交付，因此整套证据改发到 filebin（约 6 天）：

- 分卷：`https://filebin.net/alpha-d2-20261127/_s2-part1.txt` … `-part4.txt`
- 复现命令：`python project-alpha/ops/delivery/verify_bundle.py --out C:/tmp/verify3`
- 实测：`repo_files 26 / snapshot_files_written 51 / pytest_rc 0 / 91 passed in 72.18s`
- 重新发布脚本：`python project-alpha/ops/delivery/republish_all.py`（把每个交付目录重新分包上传并回写 manifests）

## 一键取全部交付物（zip）

- `https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip`（13,499,644 字节，325 个文件，sha256 `1942d21771598f39e0088c2e3838ed8b07bbe59483c9152ded32c2b7a4190e9b`）
- 解压后目录结构与本仓库一致，另外包含 `_s2/docs/`、各交付目录的 `out/` 产物与 README。
- 归档包有效期约 6 天；重新生成：`python project-alpha/ops/delivery/pack_bundle.py`（会重新打包、上传并回读校验 sha256）。

## 复核记录（2026-11-27 04:00 实测，非历史引用）

| 实例 | 命令 | 结果 |
| --- | --- | --- |
| PostgreSQL 19.0（55433，含 contrib） | `PG_PORT=55433 python -m pytest -q` | **91 passed in 66.65s** |
| PostgreSQL 16.2（55432，无 contrib） | `PG_PORT=55432 python -m pytest -q` | **83 passed, 8 skipped in 67.29s**（无 pg_trgm/btree_gist 的索引与会员期间用例跳过） |

两次都是干净跑（测试各自建一次性库、跑完 DROP），不依赖任何已有数据。
