"""Self-check: the auditor must find every issue planted in demo/index.html.

Runs the auditor on the demo page, then compares findings against the plant list
below. Exit code 0 only when every planted issue is found and no finding falls
outside the planted set (i.e. recall 1.0 and precision 1.0 on this fixture).
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "demo" / "index.html"
OUT = ROOT / "out" / "demo"

# (plant id, expected category, selector substring, why)
PLANTS = [
    ("P01", "对比度不足", "p.low-contrast-1", "灰字 #9e9e9e 落白底，2.6:1"),
    ("P02", "对比度不足", "p.low-contrast-2", "更浅的 #c8c8c8，1.67:1"),
    ("P03", "对比度不足", "a.cta", "CTA 橙色按钮白字 3.87:1"),
    ("P04", "图片缺少替代文本", "div.card > img", "img 无 alt"),
    ("P05", "链接无可读文本", "p > a", "28×28 空链接"),
    ("P06", "使用 javascript: 伪链接", "a.cta", "href=javascript:void(0)"),
    ("P07", "标题层级跳跃", "h3", "h1 直接跳 h3"),
    ("P08", "控件缺少可访问名称", "p > input", "input 无 label / placeholder"),
    ("P09", "控件缺少可访问名称", "p > button", "button 无文本"),
    ("P10", "页面缺少 lang 声明", "html", "html 无 lang"),
    ("P11", "多个 h1 主标题", "body", "两个 h1"),
    ("P12", "缺少 meta description", "head", "无 meta description"),
    ("P13", "触控目标过小", "button.tiny", "18×18 按钮"),
]


def run_audit() -> Path:
    url = DEMO.resolve().as_uri()
    subprocess.run(
        [sys.executable, str(ROOT / "pw_audit.py"), "--url", url, "--out", str(OUT), "--label", "demo"],
        check=True,
        cwd=str(ROOT),
    )
    return OUT / "findings.csv"


def main() -> int:
    csv_path = run_audit()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))

    missing = []
    for plant_id, category, selector, why in PLANTS:
        hit = any(r["category"] == category and selector in r["selector"] for r in rows)
        print(f"{'OK  ' if hit else 'MISS'} {plant_id} {category} [{selector}] {why}")
        if not hit:
            missing.append(plant_id)

    planted_categories = {p[1] for p in PLANTS}
    unexpected = [r for r in rows if r["category"] not in planted_categories]
    print(f"\nfindings={len(rows)}  plants={len(PLANTS)}  missed={len(missing)}  unexpected={len(unexpected)}")
    for r in unexpected:
        print("  unexpected:", r["id"], r["category"], r["selector"])
    return 0 if not missing and not unexpected else 1


if __name__ == "__main__":
    sys.exit(main())
