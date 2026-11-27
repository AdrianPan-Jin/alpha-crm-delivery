#!/usr/bin/env python3
"""Excel 代做交付模板：脏表 → 规范表 + 汇总 + 图表 + 处理说明。

用法：
    python clean.py 输入.csv -o 输出.xlsx --title "销售数据清洗"
    python clean.py 输入.xlsx -o 输出.xlsx --group 区域 --group 品类 --value 销售额

设计目标：客户发来一张乱表，30 分钟内出一份可直接交付的成品。
- 清掉完全空行、去首尾空格、列名规范化
- 数值列自动识别（去掉 ¥ , 空格 %），日期列自动解析
- 去重（全文重复行）
- 按指定维度出汇总透视 + 柱状图
- 单独的「处理说明」sheet，逐条写清做了什么、影响了多少行
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

CLEAN_HEADER = "1F3B57"
ACCENT = "E8601C"


def _norm_header(name: str) -> str:
    name = str(name).strip().replace("\n", " ").replace("\u3000", " ")
    name = re.sub(r"\s+", " ", name)
    return name or "未命名列"


def _to_number(series: pd.Series) -> pd.Series | None:
    """把 '¥1,234.50 ' / '12%' 这类值转成数字；识别不出就当文本。"""
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return None
    cleaned = sample.str.replace(r"[¥$,\s]", "", regex=True).str.replace("%", "", regex=False)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    if numeric.notna().mean() < 0.85:
        return None
    out = series.astype(str).str.replace(r"[¥$,\s]", "", regex=True).str.replace("%", "", regex=False)
    return pd.to_numeric(out, errors="coerce")


def _to_datetime(series: pd.Series) -> pd.Series | None:
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return None
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    if parsed.notna().mean() < 0.85:
        return None
    return pd.to_datetime(series, errors="coerce", format="mixed")


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return pd.read_excel(path, dtype=str)
    for enc in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法识别编码：{path}")


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    notes: list[str] = []
    raw_rows, raw_cols = df.shape

    df = df.dropna(how="all")
    if len(df) != raw_rows:
        notes.append(f"删除完全空行 {raw_rows - len(df)} 行")

    df.columns = [_norm_header(c) for c in df.columns]
    dup_cols = [c for c in df.columns if list(df.columns).count(c) > 1]
    if dup_cols:
        seen: dict[str, int] = {}
        cols = []
        for c in df.columns:
            seen[c] = seen.get(c, 0) + 1
            cols.append(c if seen[c] == 1 else f"{c}_{seen[c]}")
        df.columns = cols
        notes.append(f"重命名重复列名：{', '.join(sorted(set(dup_cols)))}")

    # 文本列去首尾空格与不可见字符（pandas 3.x 默认 str dtype，不能只判 object）
    def _tidy(v):
        if v is None:
            return None
        if isinstance(v, float) and pd.isna(v):
            return None
        text = str(v).replace("\u200b", "").replace("\ufeff", "").strip()
        return text or None

    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            df[col] = df[col].map(_tidy).astype("object")

    # 类型推断
    for col in list(df.columns):
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        as_dt = _to_datetime(non_null)
        if as_dt is not None and len(non_null) > 0:
            df[col] = _to_datetime(df[col])
            notes.append(f"列「{col}」按日期解析（{as_dt.dt.date.nunique()} 个不同日期）")
            continue
        as_num = _to_number(non_null)
        if as_num is not None:
            df[col] = _to_number(df[col])
            notes.append(f"列「{col}」按数值解析（含 ¥/,/空格 已清理）")

    before = len(df)
    df = df.drop_duplicates()
    if len(df) != before:
        notes.append(f"删除全文重复行 {before - len(df)} 行")

    notes.insert(0, f"读入 {raw_rows} 行 × {raw_cols} 列，输出 {len(df)} 行 × {len(df.columns)} 列")
    return df.reset_index(drop=True), notes


def build_workbook(df: pd.DataFrame, notes: list[str], out: Path, title: str,
                   groups: list[str], value: str | None) -> dict:
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    value_col = value if value in numeric else (numeric[0] if numeric else None)
    dims = [g for g in groups if g in df.columns]

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="清洗后", index=False)

        summary = None
        if dims and value_col:
            summary = df.pivot_table(index=dims, values=value_col, aggfunc="sum").reset_index()
            summary = summary.sort_values(value_col, ascending=False)
            summary.to_excel(writer, sheet_name="汇总", index=False)

        legend = pd.DataFrame({"处理步骤": notes})
        legend.to_excel(writer, sheet_name="处理说明", index=False)

    wb = load_workbook(out)
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=CLEAN_HEADER)
            cell.alignment = Alignment(vertical="center")
        for col_idx, col in enumerate(ws.iter_cols(min_row=1, max_row=1), start=1):
            width = max(10, min(38, int(len(str(col[0].value)) * 2.2 + 6)))
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    if summary is not None and len(summary) > 1:
        ws = wb["汇总"]
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = f"{value_col} 汇总"
        chart.y_axis.title = value_col
        chart.x_axis.title = " / ".join(dims)
        data = Reference(ws, min_col=len(dims) + 1, min_row=1, max_row=min(len(summary) + 1, 21))
        cats = Reference(ws, min_col=1, min_row=2, max_row=min(len(summary) + 1, 21))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.height, chart.width = 9, 20
        ws.add_chart(chart, f"A{len(summary) + 4}")

    ws = wb["处理说明"]
    ws.insert_rows(1)
    ws["A1"] = f"{title}｜处理说明（{dt.date.today().isoformat()}）"
    ws["A1"].font = Font(bold=True, size=13, color=CLEAN_HEADER)
    for cell in ws[2]:
        cell.fill = PatternFill("solid", fgColor=ACCENT)
        cell.font = Font(bold=True, color="FFFFFF")

    wb.save(out)
    return {
        "out": str(out),
        "rows": len(df),
        "cols": len(df.columns),
        "summary_rows": 0 if summary is None else len(summary),
        "value_col": value_col,
        "dims": dims,
        "notes": notes,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="脏表 → 规范表 + 汇总 + 图表")
    ap.add_argument("source")
    ap.add_argument("-o", "--out", default="cleaned.xlsx")
    ap.add_argument("--title", default="数据清洗与汇总")
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--value", default=None)
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        raise SystemExit(f"找不到文件：{src}")

    raw = load_table(src)
    df, notes = clean(raw)
    info = build_workbook(df, notes, Path(args.out), args.title, args.group, args.value)
    print({k: v for k, v in info.items() if k != "notes"})
    for n in info["notes"]:
        print(" -", n)


if __name__ == "__main__":
    main()
