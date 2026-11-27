"""Import bank statement files into ``bank_transactions``.

Rules that the client's acceptance criteria pin down:
  * two column-mapping templates (different banks, different headers)
  * only credit (income) rows are imported, debit rows are skipped
  * amounts are parsed with ``Decimal`` and stored as integer cents (never float)
  * duplicates are detected by (receiving account, bank serial number)
  * errors are recorded per line with the line number and a reason, and never
    abort the whole batch
"""
from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from . import db

TEMPLATE_KEYS = ("date", "amount", "direction", "counterparty_name", "counterparty_account", "memo", "bank_serial")
CHUNK = 1000


@dataclass
class Template:
    code: str
    name: str
    account: str
    columns: dict[str, str]
    credit_values: tuple[str, ...] = ("贷", "C", "credit", "收入", "进账")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Template":
        missing = [k for k in ("code", "name", "account", "columns") if k not in data]
        if missing:
            raise ValueError(f"模板缺少字段: {', '.join(missing)}")
        cols = data["columns"]
        unknown = [k for k in cols if k not in TEMPLATE_KEYS]
        if unknown:
            raise ValueError(f"模板列映射含未知字段: {', '.join(unknown)}")
        absent = [k for k in ("date", "amount", "bank_serial") if k not in cols]
        if absent:
            raise ValueError(f"模板列映射缺少必填字段: {', '.join(absent)}")
        return cls(
            code=str(data["code"]),
            name=str(data["name"]),
            account=str(data["account"]),
            columns={k: str(v) for k, v in cols.items()},
            credit_values=tuple(data.get("credit_values") or cls.credit_values),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "Template":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class ImportResult:
    batch_id: str
    total_rows: int = 0
    added: int = 0
    skipped_duplicate: int = 0
    skipped_debit: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    elapsed_s: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_rows": self.total_rows,
            "added": self.added,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_debit": self.skipped_debit,
            "errors": self.errors,
            "elapsed_s": round(self.elapsed_s, 3),
        }


# --------------------------------------------------------------------- parsing
def parse_amount_to_cents(raw: str) -> int:
    """`"1,234.56"` / `"1234.56元"` / `"-8.00"` -> integer cents.

    Decimal is used end to end; floats are never involved. Half-up rounding
    applies so that a bank file with 3 decimals still lands on a whole cent.
    """
    text = (raw or "").strip().replace(",", "").replace("，", "")
    text = text.replace("¥", "").replace("￥", "").replace("元", "").replace(" ", "")
    if text in ("", "-", "--"):
        raise ValueError("金额为空")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:  # noqa: TRY003 - message is the point
        raise ValueError(f"金额无法解析: {raw!r}") from exc
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_date(raw: str) -> date:
    text = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"日期无法解析: {raw!r}")


def is_credit(raw: str, credit_values: Iterable[str]) -> bool:
    text = (raw or "").strip()
    if not text:
        # 没有方向列时按贷方处理，由模板责任方保证
        return True
    lowered = text.lower()
    return any(text == c or lowered == c.lower() for c in credit_values)


def read_table(path: str | Path) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    """Return header + [(excel_row_number, {header: value})] for CSV or XLSX."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    if file_path.suffix.lower() == ".csv":
        data = file_path.read_bytes()
        text = None
        for enc in ("utf-8-sig", "gb18030", "utf-8"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("CSV 编码无法识别（尝试 utf-8-sig / gb18030）")
        reader = csv.DictReader(io.StringIO(text))
        header = [h.strip() for h in (reader.fieldnames or [])]
        rows = [(i + 2, {k.strip(): (v or "").strip() for k, v in r.items() if k}) for i, r in enumerate(reader)]
        return header, rows

    if file_path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        wb = load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in next(rows_iter)]
        rows = []
        for i, values in enumerate(rows_iter, start=2):
            if values is None:
                continue
            record = {}
            for key, value in zip(header, values):
                if key:
                    record[key] = "" if value is None else str(value).strip()
            rows.append((i, record))
        wb.close()
        return header, rows

    raise ValueError(f"不支持的文件类型: {file_path.suffix}")


# -------------------------------------------------------------------- database
def ensure_template(template: Template, org_id: str) -> str:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into bank_statement_templates (org_id, code, name, account_no, column_map)
                values (%s, %s, %s, %s, %s::jsonb)
                on conflict (org_id, code) do update
                   set name = excluded.name,
                       account_no = excluded.account_no,
                       column_map = excluded.column_map,
                       deleted_at = null
                returning id
                """,
                (org_id, template.code, template.name, template.account, json.dumps(template.columns, ensure_ascii=False)),
            )
            row = cur.fetchone()
            conn.commit()
            return str(row["id"])


def create_batch(org_id: str, template_id: str, file_name: str) -> str:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into bank_import_batches (org_id, template_id, file_name, status)
                values (%s, %s, %s, 'running') returning id
                """,
                (org_id, template_id, file_name),
            )
            batch_id = str(cur.fetchone()["id"])
            conn.commit()
            return batch_id


def finish_batch(result: ImportResult, status: str = "succeeded") -> None:
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update bank_import_batches
                   set status = %s, total_rows = %s, added = %s,
                       skipped_duplicate = %s, errors = %s::jsonb, finished_at = now()
                 where id = %s
                """,
                (
                    status,
                    result.total_rows,
                    result.added,
                    result.skipped_duplicate,
                    json.dumps(result.errors, ensure_ascii=False),
                    result.batch_id,
                ),
            )
            conn.commit()


# ---------------------------------------------------------------------- import
def import_file(
    template: Template,
    file_path: str | Path,
    *,
    org_id: str = "11111111-1111-1111-1111-111111111111",
    file_name: str | None = None,
    batch_id: str | None = None,
) -> ImportResult:
    started = time.perf_counter()
    if batch_id is None:
        template_id = ensure_template(template, org_id)
        batch_id = create_batch(org_id, template_id, file_name or Path(file_path).name)
    result = ImportResult(batch_id=batch_id)

    header, rows = read_table(file_path)
    missing_cols = [c for c in template.columns.values() if c not in header]
    if missing_cols:
        result.errors.append({"line": 1, "reason": f"文件缺少列: {', '.join(missing_cols)}"})
        result.elapsed_s = time.perf_counter() - started
        finish_batch(result, status="failed")
        return result

    result.total_rows = len(rows)
    to_insert: list[tuple] = []
    for line_no, row in rows:
        try:
            if not is_credit(row.get(template.columns.get("direction", ""), ""), template.credit_values):
                result.skipped_debit += 1
                continue
            serial = row.get(template.columns["bank_serial"], "")
            if not serial:
                raise ValueError("银行流水号为空")
            occurred = parse_date(row.get(template.columns["date"], ""))
            cents = parse_amount_to_cents(row.get(template.columns["amount"], ""))
            if cents < 0:
                raise ValueError(f"贷方金额为负数: {cents}")
            to_insert.append(
                (
                    org_id,
                    result.batch_id,
                    template.account,
                    serial,
                    occurred,
                    cents,
                    "credit",
                    row.get(template.columns.get("counterparty_name", ""), ""),
                    row.get(template.columns.get("counterparty_account", ""), ""),
                    row.get(template.columns.get("memo", ""), ""),
                )
            )
        except ValueError as exc:
            result.errors.append({"line": line_no, "reason": str(exc)})

    if to_insert:
        with db.connect() as conn:
            with conn.cursor() as cur:
                for start in range(0, len(to_insert), CHUNK):
                    chunk = to_insert[start : start + CHUNK]
                    cur.executemany(
                        """
                        insert into bank_transactions
                            (org_id, batch_id, account_no, bank_serial, occurred_on, amount_cents,
                             direction, counterparty_name, counterparty_account, memo)
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        on conflict (org_id, account_no, bank_serial) where deleted_at is null
                        do nothing
                        """,
                        chunk,
                    )
                    result.added += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            conn.commit()
        result.skipped_duplicate = len(to_insert) - result.added

    result.elapsed_s = time.perf_counter() - started
    finish_batch(result)
    return result
