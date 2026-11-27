"""Evaluation: train on one half, measure recall/precision on the other half."""

from __future__ import annotations

import json
from pathlib import Path

from .merge import merge
from .model import train_from_docs
from .schema import CATEGORIES


def _overlaps(a: dict, b: dict) -> bool:
    return a["category"] == b["category"] and a["start"] < b["end"] and b["start"] < a["end"]


def evaluate(docs: list[dict], split: float = 0.5, threshold: float = 0.5, seed: int = 20261127):
    n_train = int(len(docs) * split)
    train, test = docs[:n_train], docs[n_train:]
    model, n_samples, _ = train_from_docs(train)

    tp = fp = fn = 0
    per_cat = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CATEGORIES}
    failed = []
    for doc in test:
        stats = merge(doc["id"], doc["text"], model, threshold=threshold)
        preds = [{"start": f.span.start, "end": f.span.end, "category": f.span.category} for f in stats.findings]
        gold = doc["spans"]
        matched_gold = set()
        for p in preds:
            hit = [i for i, g in enumerate(gold) if _overlaps(p, g)]
            if hit:
                tp += 1
                per_cat[p["category"]]["tp"] += 1
                matched_gold.update(hit)
            else:
                fp += 1
                per_cat[p["category"]]["fp"] += 1
                failed.append({"doc": doc["id"], "type": "false_positive", "pred": p})
        for i, g in enumerate(gold):
            if i not in matched_gold:
                fn += 1
                per_cat[g["category"]]["fn"] += 1
                failed.append({"doc": doc["id"], "type": "false_negative", "gold": g})

    recall = tp / (tp + fn) if tp + fn else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    per_cat_metrics = {
        c: {
            "recall": (v["tp"] / (v["tp"] + v["fn"])) if (v["tp"] + v["fn"]) else None,
            "precision": (v["tp"] / (v["tp"] + v["fp"])) if (v["tp"] + v["fp"]) else None,
            "support": v["tp"] + v["fn"],
        }
        for c, v in per_cat.items()
    }
    return {
        "n_train_docs": len(train),
        "n_test_docs": len(test),
        "training_candidates": n_samples,
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "per_category": per_cat_metrics,
        "failed_examples": failed[:10],
    }


def write_report(metrics: dict, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 敏感内容复查：规则 + 模型合并管线 评测报告",
        "",
        f"- 训练文档 {metrics['n_train_docs']} / 评测文档 {metrics['n_test_docs']}（虚构数据集）",
        f"- 阈值 {metrics['threshold']}，训练候选样本 {metrics['training_candidates']}",
        f"- **recall = {metrics['recall']:.4f}**（tp={metrics['tp']}, fn={metrics['fn']}）",
        f"- **precision = {metrics['precision']:.4f}**（tp={metrics['tp']}, fp={metrics['fp']}）",
        "",
        "## 分类别",
        "| 类别 | recall | precision | support |",
        "|---|---|---|---|",
    ]
    for c, m in metrics["per_category"].items():
        r = "—" if m["recall"] is None else f"{m['recall']:.4f}"
        p = "—" if m["precision"] is None else f"{m['precision']:.4f}"
        lines.append(f"| {c} | {r} | {p} | {m['support']} |")
    if metrics["failed_examples"]:
        lines += ["", "## 失败样例（前 10 条，供人工复核）", ""]
        for ex in metrics["failed_examples"]:
            lines.append(f"- `{ex}`")
    p = out / "eval_report.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p, out / "metrics.json"


if __name__ == "__main__":
    import argparse

    from .dataset import load_jsonl

    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="data/eval_set.jsonl")
    ap.add_argument("--out", default="out")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--split", type=float, default=0.5)
    a = ap.parse_args()
    docs = load_jsonl(a.set)
    m = evaluate(docs, split=a.split, threshold=a.threshold)
    rp, mp = write_report(m, a.out)
    print(f"recall={m['recall']} precision={m['precision']} tp={m['tp']} fp={m['fp']} fn={m['fn']}")
    print("report:", rp)
