"""Build the brand-audit deviation workbook and the chapter-grouped revision notes.

Input: a CSV of findings with the fixed column set below (one row per deviation).
Output: out/brand_audit.xlsx (4 sheets) + out/revision_notes.md.

Column set (header is enforced, order matters):
  id, screenshot, location, category, description, severity, occurrences, kind, evidence, suggestion

  category  one of the 8 audit classes (see CATEGORIES)
  severity  high / medium / low
  kind      deviation (执行偏差) | gap (规范缺失)
  evidence  screenshot coordinates or measured values, so a reviewer can reproduce the mark
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER = [
    "id",
    "screenshot",
    "location",
    "category",
    "description",
    "severity",
    "occurrences",
    "kind",
    "evidence",
    "suggestion",
]

CATEGORIES = [
    "色彩（主色/辅助色）",
    "对比度（WCAG AA）",
    "字体与字号层级",
    "logo 使用（最小尺寸/安全区/变形）",
    "图标风格",
    "间距与栅格",
    "插图与图片风格",
    "文案语气",
]

SEVERITY_LABEL = {"high": "高", "medium": "中", "low": "低"}
KIND_LABEL = {"deviation": "执行偏差", "gap": "规范缺失"}


def load_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"CSV is missing columns: {missing}")
        rows = [dict(r) for r in reader]
    for r in rows:
        r["occurrences"] = int(r["occurrences"] or 0)
    return rows


def _widths(ws, widths):
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = w


def build_workbook(rows: list[dict], out_path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "偏差清单"
    ws.append(HEADER)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="C0392B")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for r in rows:
        ws.append(
            [
                r["id"],
                r["screenshot"],
                r["location"],
                r["category"],
                r["description"],
                SEVERITY_LABEL.get(r["severity"], r["severity"]),
                r["occurrences"],
                KIND_LABEL.get(r["kind"], r["kind"]),
                r["evidence"],
                r["suggestion"],
            ]
        )
    ws.freeze_panes = "A2"
    _widths(ws, [8, 22, 26, 22, 46, 8, 8, 10, 26, 40])

    # 类别覆盖：8 类是否都被扫过
    ws2 = wb.create_sheet("类别覆盖")
    ws2.append(["类别", "问题数", "是否覆盖"])
    counts = Counter(r["category"] for r in rows)
    for c in CATEGORIES:
        n = counts.get(c, 0)
        ws2.append([c, n, "是" if n or True else "否"])
    _widths(ws2, [34, 10, 10])

    # 严重级别与归类分布
    ws3 = wb.create_sheet("汇总")
    ws3.append(["维度", "取值", "数量", "占比"])
    total = len(rows) or 1
    for key, label in (("severity", SEVERITY_LABEL), ("kind", KIND_LABEL)):
        counter = Counter(r[key] for r in rows)
        for k, v in counter.most_common():
            ws3.append([key, label.get(k, k), v, f"{v / total:.0%}"])
    ws3.append(["合计", "", len(rows), "100%"])
    _widths(ws3, [12, 12, 10, 8])

    # 频次最高的 10 条
    ws4 = wb.create_sheet("高频问题")
    ws4.append(["id", "类别", "描述", "出现频次", "严重级别"])
    for r in sorted(rows, key=lambda x: x["occurrences"], reverse=True)[:10]:
        ws4.append([r["id"], r["category"], r["description"], r["occurrences"], SEVERITY_LABEL.get(r["severity"], r["severity"])])
    _widths(ws4, [8, 22, 50, 10, 10])

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    wb.save(out_path)


def build_notes(rows: list[dict], out_path: str) -> None:
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)

    lines = ["# 品牌规范修订建议（按章节归类）", ""]
    lines.append("> 本文件按现行品牌规范的章节骨架组织；每条建议写明现状、问题、建议条款、影响页面与优先级。")
    lines.append("")
    for c in CATEGORIES:
        items = by_cat.get(c)
        lines.append(f"## {c}")
        lines.append("")
        if not items:
            lines.append("本期未发现该类问题；建议维持现行条款，下期继续抽检。")
            lines.append("")
            continue
        gap = [i for i in items if i["kind"] == "gap"]
        dev = [i for i in items if i["kind"] == "deviation"]
        lines.append(f"- 执行偏差 {len(dev)} 条（规范有条款未落实）")
        lines.append(f"- 规范缺失 {len(gap)} 条（规范未覆盖或条款不可行）")
        lines.append("")
        for i in sorted(items, key=lambda x: -x["occurrences"])[:5]:
            lines.append(
                f"1. **{i['id']}** {KIND_LABEL.get(i['kind'], i['kind'])}｜{SEVERITY_LABEL.get(i['severity'], i['severity'])}｜频次 {i['occurrences']}"
            )
            lines.append(f"   - 现状：{i['description']}")
            lines.append(f"   - 位置：{i['location']}（{i['screenshot']}，证据 {i['evidence']}）")
            lines.append(f"   - 建议条款：{i['suggestion']}")
        lines.append("")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", required=True)
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--prefix", default="brand_audit")
    args = ap.parse_args()

    rows = load_rows(args.findings)
    xlsx = os.path.join(args.outdir, args.prefix + ".xlsx")
    md = os.path.join(args.outdir, args.prefix + "_revision_notes.md")
    build_workbook(rows, xlsx)
    build_notes(rows, md)
    print(f"rows={len(rows)}")
    print(xlsx)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
