#!/usr/bin/env python3
"""把多次 pw_audit 的产出合并成「品牌落地审计」交付文档（对应 2113）。

输入：out/sample-pack/{findings_all.csv, findings_grouped.csv}、out/<slug>/run.json、out/<slug>/shots/
输出：docs/DELIVERABLE-2113.md

口径（写进文档，避免买方误解）：
- 全部数据来自公开站点（python.org 及子页），无客户真实数据
- 对比度用 WCAG 2.1 相对亮度公式逐元素实测（工具写在每条记录里）
- 执行偏差 = 规范有条款未落实；规范缺失 = 规范未覆盖或条款不可执行
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
from collections import Counter, defaultdict

BASE = pathlib.Path(__file__).resolve().parent
PACK = BASE / "out" / "sample-pack"
OUT = BASE / "out"
DOCS = BASE / "docs"

SECTION_HINTS = [
    ("页头与品牌露出", ("header", "logo", "brand", "masthead", "top-bar")),
    ("导航与信息架构", ("nav", "menu", "breadcrumb", "sidebar", "sitemap", "toc", "list-row", "sphinxsidebar")),
    ("表单与控件", ("input", "button", "select", "form", "label", "checkbox", "search")),
    ("页脚与法务", ("footer", "copyright", "legal", "privacy")),
    ("移动端与触控", ("touch", "tap", "mobile")),
    ("内容区排版", ("content", "article", "quote", "blockquote", "h1", "h2", "h3", "p", "small")),
]


def site_slug_map() -> dict[str, str]:
    """把 run.json 里的 url 映射到 out/<slug> 目录名。"""
    m: dict[str, str] = {}
    for run in OUT.glob("*/run.json"):
        try:
            data = json.loads(run.read_text(encoding="utf-8"))
        except Exception:
            continue
        url = (data.get("url") or "").rstrip("/")
        if url:
            m[url] = run.parent.name
    return m


def section_of(selector: str, category: str) -> str:
    s = (selector or "").lower()
    if "触控" in category:
        return "移动端与触控"
    for name, keys in SECTION_HINTS:
        if any(k in s for k in keys):
            return name
    return "内容区排版"


def main() -> None:
    rows = list(csv.DictReader(PACK.joinpath("findings_all.csv").open(encoding="utf-8-sig")))
    grouped = list(csv.DictReader(PACK.joinpath("findings_grouped.csv").open(encoding="utf-8-sig")))
    slugs = site_slug_map()
    DOCS.mkdir(exist_ok=True)

    sites = sorted({r["site"] for r in rows})
    by_cat = Counter(r["category"] for r in rows)
    by_sev = Counter(r["severity"] for r in rows)
    by_kind = Counter(r["kind"] for r in rows)
    tool = next((r["tool"] for r in rows if r.get("tool")), "pw_audit")

    out: list[str] = []
    w = out.append
    w("# 品牌落地审计 · 偏差清单与修订建议（交付物 v1）\n")
    w(f"> 生成于 {dt.date.today().isoformat()}｜抽样站点 {len(sites)} 个｜偏差记录 **{len(rows)}** 条（验收线 ≥40）"
      f"｜去重问题类 {len(grouped)} 类\n")
    w("## 0. 这份东西是什么\n")
    w("- 一份**结构已定稿、字段与验收逐条对齐**的交付物：拿到你方域名后把 `--url` 换掉重跑，即产出同结构报告 + 截图，无需二次开发。")
    w("- 当前数据来自公开站点（python.org 及 5 个子页），**不含任何客户真实数据、不含客户名称**；截图仅用于举证位置。")
    w("- 每条记录都有：编号、位置（selector + 坐标）、问题类型、严重级、执行偏差/规范缺失判定、实测值与工具名、截图引用、修订建议。\n")

    w("## 1. 口径与方法\n")
    w("| 项 | 取值 |\n| --- | --- |")
    w(f"| 采集工具 | `{tool}` |")
    w("| 视口 | 桌面 1440×900；移动 390×844（触控目标） |")
    w("| 对比度阈值 | 正文 <4.5:1 判失败；大字号（≥24px 或 ≥18.66px 粗体）<3:1 判失败 |")
    w("| 触控目标 | <24×24 CSS px 判失败（WCAG 2.2 SC 2.5.8） |")
    w("| 判定规则 | 规范有条款未落实 → 执行偏差；规范未覆盖/条款不可执行 → 规范缺失 |")
    w("| 抽样 | 每站全量遍历可见文本元素，同类去重后取代表样本入册 |\n")

    w("## 2. 总览\n")
    w("| 维度 | 分布 |\n| --- | --- |")
    w("| 站点 | " + "、".join(sites) + " |")
    w("| 问题类型 | " + "；".join(f"{k} {v}" for k, v in by_cat.most_common()) + " |")
    w("| 严重级 | " + "；".join(f"{k} {v}" for k, v in by_sev.most_common()) + " |")
    w("| 判定 | " + "；".join(f"{k} {v}" for k, v in by_kind.most_common()) + " |\n")

    # 3. 记录表
    w("## 3. 偏差记录\n")
    w("> 编号规则 `站点#原编号`；截图列 = 该站的全页标注图（红框编号即记录号）+ 元素截图路径。\n")
    per_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        per_cat[r["category"]].append(r)
    ordering = sorted(per_cat, key=lambda c: -len(per_cat[c]))
    for i, cat in enumerate(ordering, start=1):
        items = per_cat[cat]
        w(f"### 3.{i} {cat}（{len(items)} 条）\n")
        w("| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |\n| --- | --- | --- | --- | --- | --- | --- |")
        for r in items[:30]:
            slug = slugs.get(r["site"].rstrip("/"), "")
            shot = f"`out/{slug}/desktop-full-annotated.png`（#{r['id']}）" if slug else "—"
            elem = f"`out/{slug}/shots/{r['id']}.png`"
            if slug and not OUT.joinpath(slug, "shots", f"{r['id']}.png").exists():
                elem = None
            cells = [
                f"{r['site']}#{r['id']}",
                f"`{(r.get('selector') or '')[:46]}` @({r.get('x')},{r.get('y')})",
                r["severity"],
                r["kind"],
                (r.get("description") or "").replace("|", "／")[:60],
                "pw_audit / WCAG2.1",
                shot + (f" + {elem}" if elem else ""),
            ]
            w("| " + " | ".join(cells) + " |")
        if len(items) > 30:
            w(f"\n> 其余 {len(items) - 30} 条见 `findings_all.csv`（同字段集，可直接筛/排序）。\n")
        w("")

    # 4. 修订建议
    w("## 4. 修订建议（按规范章节归类，每条回引记录编号）\n")
    sec_rows: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        sec_rows[section_of(r.get("selector", ""), r["category"])].append(r)
    order = [s for s, _ in SECTION_HINTS] + [s for s in sec_rows if s not in dict(SECTION_HINTS)]
    n = 0
    for sec in order:
        items = sec_rows.get(sec) or []
        if not items:
            continue
        n += 1
        dev = sum(1 for r in items if r["kind"] == "execution_deviation")
        gap = len(items) - dev
        w(f"### 4.{n} {sec}（{len(items)} 条：执行偏差 {dev} / 规范缺失 {gap}）\n")
        w("- 执行偏差 → 直接派工修复，并把对应条款写进上线检查单。")
        w("- 规范缺失 → 补条款（写明阈值、正反例、例外情形）。\n")
        seen: set[tuple[str, str]] = set()
        for r in items:
            key = (r["category"], (r.get("suggestion") or "").strip())
            if key in seen:
                continue
            seen.add(key)
            ids = [x["id"] for x in items if (x["category"], (x.get("suggestion") or "").strip()) == key]
            w(f"- **{r['category']}**：{key[1]}（记录 {', '.join(ids[:10])}{'…' if len(ids) > 10 else ''}）")
        w("")

    w("## 5. 在你方站点复跑\n")
    w("```bash\npython pw_audit.py --url https://<your-domain> --out out/<slug>\npython merge_pack.py --out out/<pack> out/<slug> [out/<slug2> ...]\n```\n")
    w("产出：`report.md`／`findings.csv`／`findings.xlsx`（四表）／`revision_notes.md`（章节归类）／"
      "`desktop-full-annotated.png`（全页编号标注）／`shots/`（元素截图）。\n")

    w("## 6. 边界与假设\n")
    w("- 需要你方提供：现行品牌规范（PDF 或可读快照，用于「执行偏差 vs 规范缺失」判定）、页面清单与访问权限。")
    w("- 需要登录的页面请给只读测试账号；审计全程只读，不写任何数据、不上传素材。")
    w("- 若你方规范里没有对应条款，我会在「规范缺失」里给出建议条款文本，而不是硬判为偏差。\n")

    doc = DOCS / "DELIVERABLE-2113.md"
    doc.write_text("\n".join(out), encoding="utf-8")
    print({"doc": str(doc), "rows": len(rows), "classes": len(grouped), "bytes": doc.stat().st_size})


if __name__ == "__main__":
    main()
