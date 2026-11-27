#!/usr/bin/env python3
"""Excel 自动化看板模板：客户表 → 「数据 / 看板」两页，换数据按键即刷新。

用法：
    python dashboard.py 销售明细.csv -o 看板.xlsx --title "2026 销售看板" \
        --date 下单日期 --amount 金额 --dim 区域 --dim 品类

做出来的东西：
- 数据页：原始明细（不动），客户以后自己往下贴新行即可
- 看板页：4 个 KPI + 月度趋势（SUMIFS 公式，不依赖透视缓存）+ 维度 Top10 条形图
- 全部是实时公式：客户改数据 → 按 F9 或重开文件，数字与图跟着走（不需要重跑脚本）
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

INK = "1F3B57"
ACCENT = "E8601C"
MIST = "EEF1F5"
LINE = "D8DBE0"

FONT_CN = "Microsoft YaHei"


def _fill(color: str) -> PatternFill:
    return PatternFill("solid", fgColor=color)


def _thin() -> Border:
    side = Side(style="thin", color=LINE)
    return Border(left=side, right=side, top=side, bottom=side)


def read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return pd.read_excel(path)
    for enc in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法识别编码：{path}")


def month_key(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m")


def write_data_sheet(wb: Workbook, df: pd.DataFrame) -> None:
    ws = wb.active
    ws.title = "数据"
    ws.append([str(c) for c in df.columns])
    for row in df.itertuples(index=False):
        ws.append([None if pd.isna(v) else v for v in row])

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF", name=FONT_CN, size=10)
        cell.fill = _fill(INK)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for idx, col in enumerate(df.columns, start=1):
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            for row in range(2, len(df) + 2):
                ws.cell(row=row, column=idx).number_format = "yyyy-mm-dd"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    for idx, col in enumerate(df.columns, start=1):
        width = max(10, min(28, int(max(len(str(col)), *(len(str(v)) for v in df[col].head(50) if pd.notna(v))) * 1.6 + 4)))
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.sheet_view.zoomScale = 90


def build_dashboard(wb: Workbook, df: pd.DataFrame, date_col: str, amount_col: str, dims: list[str], title: str) -> dict:
    ws = wb.create_sheet("看板")
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 90
    for col, width in (("A", 3), ("B", 22), ("C", 16), ("D", 16), ("E", 22), ("F", 16), ("G", 16)):
        ws.column_dimensions[col].width = width

    nrows = len(df) + 1  # 含表头
    amount_range = f"数据!${_col(amount_col)}$2:${_col(amount_col)}${nrows}"
    date_range = f"数据!${_col(date_col)}$2:${_col(date_col)}${nrows}"

    ws["B2"] = title
    ws["B2"].font = Font(bold=True, size=18, color=INK, name=FONT_CN)
    dmin = pd.to_datetime(df[date_col]).min().strftime("%Y-%m-%d")
    dmax = pd.to_datetime(df[date_col]).max().strftime("%Y-%m-%d")
    ws["B3"] = f"数据区间：{dmin} ~ {dmax}｜明细 {len(df)} 行｜生成于 {dt.date.today().isoformat()}"
    ws["B3"].font = Font(size=9, color="6B7785", name=FONT_CN)

    kpis = [
        ("总金额", f"=SUM({amount_range})", "#,##0"),
        ("订单数", f"=COUNTA({date_range})", "#,##0"),
        ("客单价", "=IFERROR(B6/D6,0)", "#,##0.0"),
        ("最大单笔", f"=MAX({amount_range})", "#,##0"),
    ]
    for i, (label, formula, fmt) in enumerate(kpis):
        x = 2 + (i % 2) * 2
        y = 5 + (i // 2) * 3
        cell = ws.cell(row=y, column=x, value=label)
        cell.font = Font(size=9, color="6B7785", name=FONT_CN)
        val = ws.cell(row=y + 1, column=x, value=formula)
        val.font = Font(bold=True, size=16, color=ACCENT, name=FONT_CN)
        val.number_format = fmt
        for r in (y, y + 1):
            for c in (x, x + 1):
                ws.cell(row=r, column=c).fill = _fill(MIST)
                ws.cell(row=r, column=c).border = _thin()

    # 月度趋势（SUMIFS，不依赖透视缓存）
    months = sorted({m for m in month_key(df[date_col]).dropna()})
    start = 5
    ws.cell(row=start - 1, column=8, value="月份").font = Font(bold=True, size=10, name=FONT_CN)
    ws.cell(row=start - 1, column=9, value="金额").font = Font(bold=True, size=10, name=FONT_CN)
    for i, month in enumerate(months[:24], start=start):
        ws.cell(row=i, column=8, value=month).font = Font(size=9, name=FONT_CN)
        cell = ws.cell(
            row=i,
            column=9,
            value=f'=SUMIFS({amount_range},{date_range},">="&DATEVALUE("{month}-01"),{date_range},"<="&EOMONTH(DATEVALUE("{month}-01"),0))',
        )
        cell.number_format = "#,##0"
        cell.font = Font(size=9, name=FONT_CN)

    line = LineChart()
    line.title = "月度金额趋势"
    line.height, line.width = 8.5, 15
    line.y_axis.title = "金额"
    data = Reference(ws, min_col=9, min_row=start - 1, max_row=start + len(months[:24]) - 1)
    cats = Reference(ws, min_col=8, min_row=start, max_row=start + len(months[:24]) - 1)
    line.add_data(data, titles_from_data=True)
    line.set_categories(cats)
    line.series[0].graphicalProperties.line.width = 22000
    line.series[0].graphicalProperties.line.solidFill = ACCENT
    line.series[0].graphicalProperties.line.color = ACCENT
    ws.add_chart(line, "B12")

    # 维度 Top10
    bar_rows = []
    if dims:
        dim = dims[0]
        agg = df.groupby(dim, dropna=False)[amount_col].sum().sort_values(ascending=False).head(10)
        hcol = 8
        hrow = start + len(months[:24]) + 4
        ws.cell(row=hrow - 1, column=hcol, value=dim).font = Font(bold=True, size=10, name=FONT_CN)
        ws.cell(row=hrow - 1, column=hcol + 1, value="金额").font = Font(bold=True, size=10, name=FONT_CN)
        for i, (name, val) in enumerate(agg.items(), start=hrow):
            ws.cell(row=i, column=hcol, value=str(name)).font = Font(size=9, name=FONT_CN)
            cell = ws.cell(row=i, column=hcol + 1, value=float(val))
            cell.number_format = "#,##0"
            cell.font = Font(size=9, name=FONT_CN)
            bar_rows.append(i)

        bar = BarChart()
        bar.type = "bar"
        bar.title = f"{dim} Top10"
        bar.height, bar.width = 8.5, 15
        d = Reference(ws, min_col=hcol + 1, min_row=hrow - 1, max_row=hrow - 1 + len(bar_rows))
        c = Reference(ws, min_col=hcol, min_row=hrow, max_row=hrow - 1 + len(bar_rows))
        bar.add_data(d, titles_from_data=True)
        bar.set_categories(c)
        bar.legend = None
        for ser in bar.series:
            ser.graphicalProperties.solidFill = INK
            ser.graphicalProperties.line.solidFill = INK
        ws.add_chart(bar, f"B{12 + 18}")

    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws["B4"] = "把新的明细粘到「数据」页（保持表头），按 F9 刷新即可"
    ws["B4"].font = Font(size=9, italic=True, color="6B7785", name=FONT_CN)
    return {"months": len(months[:24]), "top_rows": len(bar_rows)}


def _col(name: str) -> str:
    """列名 → Excel 列字母（按 1 起计）。"""
    from openpyxl.utils import column_index_from_string  # noqa: F401

    letters = ""
    idx = _COL_INDEX[name]
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


_COL_INDEX: dict[str, int] = {}


def main() -> None:
    ap = argparse.ArgumentParser(description="客户表 → 自动化看板")
    ap.add_argument("source")
    ap.add_argument("-o", "--out", default="dashboard.xlsx")
    ap.add_argument("--title", default="经营看板")
    ap.add_argument("--date", required=True)
    ap.add_argument("--amount", required=True)
    ap.add_argument("--dim", action="append", default=[])
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        raise SystemExit(f"找不到文件：{src}")
    df = read_source(src)
    for col in (args.date, args.amount):
        if col not in df.columns:
            raise SystemExit(f"列不存在：{col}（可用列：{list(df.columns)}）")

    clean_df = df.copy()
    clean_df[args.date] = pd.to_datetime(clean_df[args.date], errors="coerce")
    clean_df = clean_df.dropna(subset=[args.date])
    clean_df = clean_df[clean_df[args.amount].notna()]

    _COL_INDEX.clear()
    _COL_INDEX.update({str(c): i for i, c in enumerate(clean_df.columns, start=1)})

    wb = Workbook()
    write_data_sheet(wb, clean_df)
    info = build_dashboard(wb, clean_df, args.date, args.amount, [d for d in args.dim if d in clean_df.columns], args.title)
    wb.save(args.out)
    print({"out": args.out, "rows": len(clean_df), **info})


if __name__ == "__main__":
    main()
