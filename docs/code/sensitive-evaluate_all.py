"""Evaluate on all three fictional sets (normal / hard / stress) and report per set.

The buyer's AC asks for recall >= 0.95 and precision >= 0.60 on the fictional
evaluation set; this script prints those numbers per set and in aggregate so the
report is honest about which formats are covered.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import build_docs, build_hard_docs, build_stress_docs, write_jsonl
from .evaluate import evaluate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--n", type=int, default=40, help="docs per set")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    sets = {
        "normal": build_docs(a.n, 20261127),
        "hard": build_hard_docs(a.n, 20261128),
        "stress": build_stress_docs(a.n, 20261129),
    }
    combined = [d for docs in sets.values() for d in docs]

    rows = {}
    for name, docs in list(sets.items()) + [("combined", combined)]:
        m = evaluate(docs)
        rows[name] = {
            "docs": len(docs),
            "spans": sum(len(d["spans"]) for d in docs),
            "recall": round(m["recall"], 4),
            "precision": round(m["precision"], 4),
            "tp": m["tp"], "fp": m["fp"], "fn": m["fn"],
            "per_category": {k: dict(v) for k, v in m["per_category"].items()},
        }

    (out / "metrics_all.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 敏感内容复查：三套虚构评测集结果", "",
             "| 评测集 | 文档 | 标注片段 | recall | precision | tp | fp | fn |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, r in rows.items():
        lines.append(f"| {name} | {r['docs']} | {r['spans']} | {r['recall']:.4f} | {r['precision']:.4f} | {r['tp']} | {r['fp']} | {r['fn']} |")
    lines += ["", "## 分类别（combined）", "", "| 类别 | recall | precision | support |", "| --- | --- | --- | --- |"]
    def f4(x):
        return f"{x:.4f}" if isinstance(x, (int, float)) else "n/a"

    for cat, v in rows["combined"]["per_category"].items():
        lines.append(f"| {cat} | {f4(v.get('recall'))} | {f4(v.get('precision'))} | {v.get('support')} |")
    lines += ["", "口径：训练集与测试集各半（split=0.5），阈值 0.5；命中判定为「同类别且区间重叠」。", ""]
    (out / "eval_all.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
