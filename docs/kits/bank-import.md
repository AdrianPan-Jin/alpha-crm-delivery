# 银行到账流水导入（S4-FIN-011 交付物）

多模板字段映射 + 只导贷方 + Decimal 转分 + （收款账户, 银行流水号）去重 + 异步批次 + 5000 行 60 秒内完成。

## 快速开始

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
createdb -h 127.0.0.1 -p 55433 -U postgres bank_demo      # 本地 PG19
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.bank.cli --template samples/template-bank-a.json --file samples/bank-a-2026-10.csv
```

## 模板

`samples/template-bank-a.json` 与 `template-bank-b.json` 各描述一家虚构银行的列名与方向取值，
字段：交易日期、金额、借贷方向、对方户名、对方账号、附言、银行流水号（收款账户来自模板的 `account`）。

## 接口

- `POST /api/finance/bank-imports`：`{template_id, file_path}` → 建批次并异步跑（返回 batch_id）
- `GET /api/finance/bank-imports/{id}`：批次状态（added / skipped_duplicate / errors[{line, reason}]）

## 验收自检

| AC | 对应测试 |
| --- | --- |
| 2 种模板样例各自导入成功、金额转分逐分正确 | `tests/test_import.py::test_template_a_cents_exact` / `test_template_b_cents_exact` |
| 同一文件重复导入新增数为 0 | `test_reimport_adds_zero` |
| 借方记录不被导入 | `test_debit_rows_skipped` |
| 5000 行 < 60 秒 | `test_5000_rows_under_60s`（输出计时日志） |
