# -*- coding: utf-8 -*-
"""Merge several pw_audit runs into one client-shaped sample pack.

Why: task 2113 asks for >=40 findings on the client's own materials. We cannot
have their materials yet, so we publish an equivalent pack from public sites that
shows the exact output shape and volume we deliver (>=40 findings, each with
annotated screenshot, location, category, severity, execution-vs-spec judgement,
measured evidence and a spec-section-grouped revision note).

Usage: python merge_pack.py --merge "python.org=out/pyorg4,docs.python.org=out/docs3,..." --out out/sample-pack
"""
import argparse
import csv
import json
import os
import shutil
import zipfile
from collections import Counter


def read_findings(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", required=True, help="label=outdir,...")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    merged, per_site = [], {}
    for item in args.merge.split(","):
        label, d = item.split("=", 1)
        fp = os.path.join(d, "findings.csv")
        if not os.path.exists(fp):
            print("skip missing", fp)
            continue
        rows = read_findings(fp)
        for r in rows:
            r["site"] = label
        per_site[label] = rows
        merged += rows
        shots = os.path.join(d, "shots")
        if os.path.isdir(shots):
            dst = os.path.join(args.out, "shots", label)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(shots, dst)

    fields = ["id", "site", "section", "category", "severity", "kind", "selector", "x", "y", "w", "h",
              "description", "evidence", "suggestion", "screenshot", "tool"]
    with open(os.path.join(args.out, "findings_all.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in merged:
            w.writerow({k: r.get(k, "") for k in fields})

    # group identical issues (same category/selector/evidence) so a client sees
    # "one issue, N occurrences" instead of 40 near-identical rows
    groups = {}
    for r in merged:
        key = (r.get("site", ""), r.get("category", ""), r.get("selector", ""), r.get("evidence", ""))
        g = groups.setdefault(key, {"screen_count": 0, "ids": [], "sample": r})
        g["screen_count"] += 1
        g["ids"].append(r.get("id", ""))
    with open(os.path.join(args.out, "findings_grouped.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["site", "category", "severity", "kind", "selector", "description", "evidence",
                    "suggestion", "count", "sample_ids"])
        for (site, cat, sel, ev), g in sorted(groups.items(), key=lambda kv: -kv[1]["screen_count"]):
            r = g["sample"]
            w.writerow([site, cat, r.get("severity", ""), r.get("kind", ""), sel, r.get("description", ""),
                        ev, r.get("suggestion", ""), g["screen_count"], ",".join(g["ids"][:5])])

    by_cat = Counter(r.get("category", "") for r in merged)
    by_sev = Counter(r.get("severity", "") for r in merged)
    by_kind = Counter(r.get("kind", "") for r in merged)

    lines = ["# 样本包：多站点品牌落地审计（形状与体量等同于 2113 交付物）", "",
             f"- 站点数：{len(per_site)}", f"- 偏差条目：**{len(merged)}** 条（验收要求 ≥40）",
             f"- 去重后问题类：**{len(groups)}** 类（同类问题按出现次数计数，见 `findings_grouped.csv`）", "",
             "| 站点 | 条目 |", "| --- | --- |"]
    for k, v in per_site.items():
        lines.append(f"| {k} | {len(v)} |")
    lines += ["", "## 类别覆盖", "", "| category | 条数 |", "| --- | --- |"]
    for k, v in by_cat.most_common():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 严重级分布", "", "| severity | 条数 |", "| --- | --- |"]
    for k, v in by_sev.most_common():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 判定分布（执行偏差 vs 规范缺失）", "", "| kind | 条数 |", "| --- | --- |"]
    for k, v in by_kind.most_common():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 每条包含",
              "",
              "- 编号、站点、位置（selector + 视口坐标）、类别、严重级",
              "- 判定：`execution_deviation`（规范有条款未落实）/ `specification_gap`（规范未覆盖或不可行）",
              "- 实测证据：对比度给出前景/背景色值、实测比值、字号字重与 WCAG 2.1 阈值",
              "- 元素级截图（`shots/<site>/<id>.png`）与全页标注图（各站点 `desktop-full-annotated.png`）",
              "- 按规范章节归类的修订建议（回引编号）"]
    open(os.path.join(args.out, "SUMMARY.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    for label, d in [x.split("=", 1) for x in args.merge.split(",")]:
        for f in ("desktop-full-annotated.png", "report.md", "revision_notes.md", "run.json"):
            src = os.path.join(d, f)
            if os.path.exists(src):
                dst_dir = os.path.join(args.out, "full", label)
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src, os.path.join(dst_dir, f))

    zpath = os.path.join(args.out, "sample-pack.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for cur, _dirs, files in os.walk(args.out):
            for f in files:
                if f.endswith(".zip"):
                    continue
                p = os.path.join(cur, f)
                z.write(p, os.path.relpath(p, args.out))
    print(json.dumps({"findings": len(merged), "categories": dict(by_cat), "severity": dict(by_sev),
                      "zip": zpath, "zip_bytes": os.path.getsize(zpath)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
