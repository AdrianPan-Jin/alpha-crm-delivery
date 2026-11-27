"""Read-only consistency rules for the daily check (S4-FIN/GO ticket 2964).

Every rule is a single read-only SELECT that returns the offending rows. The
engine never writes: it opens a READ ONLY transaction, runs each enabled rule,
and reports counts + a bounded sample of rows.

Rule file format (YAML):

    rules:
      - id: contacts_on_deleted_company
        title: 联系人挂在已删除企业上
        severity: high          # high | medium | low
        sql: SELECT ... LIMIT 50
        enabled: true
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import psycopg

SEVERITIES = ("high", "medium", "low")
SAMPLE_LIMIT = 50


@dataclass
class Rule:
    id: str
    title: str
    sql: str
    severity: str = "medium"
    enabled: bool = True
    description: str = ""


@dataclass
class RuleResult:
    rule: Rule
    rows: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.rule.id,
            "title": self.rule.title,
            "severity": self.rule.severity,
            "count": self.count,
            "sample": self.rows[:SAMPLE_LIMIT],
            "error": self.error,
        }


def load_rules(path: str | Path) -> list[Rule]:
    """Load rules from YAML; ``yaml`` is imported lazily so the module stays importable."""
    import yaml  # noqa: PLC0415

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rules: list[Rule] = []
    for raw in data.get("rules", []):
        severity = str(raw.get("severity", "medium")).lower()
        if severity not in SEVERITIES:
            raise ValueError(f"rule {raw.get('id')}: severity must be one of {SEVERITIES}")
        sql = str(raw["sql"]).strip().rstrip(";")
        if not sql.lower().startswith("select") and not sql.lower().startswith("with"):
            raise ValueError(f"rule {raw['id']}: only SELECT / WITH statements are allowed")
        rules.append(
            Rule(
                id=str(raw["id"]),
                title=str(raw.get("title", raw["id"])),
                sql=sql,
                severity=severity,
                enabled=bool(raw.get("enabled", True)),
                description=str(raw.get("description", "")),
            )
        )
    return rules


def run_rule(conn: psycopg.Connection, rule: Rule) -> RuleResult:
    result = RuleResult(rule=rule)
    try:
        # READ ONLY keeps the daily check incapable of mutating data, by construction
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            cur = conn.execute(rule.sql)
            cols = [d.name for d in cur.description or []]
            rows = cur.fetchall()
        result.rows = [dict(zip(cols, r)) for r in rows[:SAMPLE_LIMIT]]
        result.count = len(rows)
    except Exception as exc:  # noqa: BLE001 - a broken rule must not kill the run
        conn.rollback()
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def run_all(
    conn: psycopg.Connection, rules: Iterable[Rule]
) -> tuple[list[RuleResult], int]:
    results = [run_rule(conn, r) for r in rules if r.enabled]
    findings = sum(r.count for r in results)
    return results, findings


def send_webhook(url: str, payload: dict[str, Any], timeout: float = 10.0) -> bool:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - operator-supplied URL
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001 - webhook failures are reported, not raised
        return False


def summary(results: list[RuleResult], findings: int) -> dict[str, Any]:
    by_severity: dict[str, int] = {s: 0 for s in SEVERITIES}
    for r in results:
        if r.count:
            by_severity[r.rule.severity] += r.count
    return {
        "ok": findings == 0,
        "findings": findings,
        "by_severity": by_severity,
        "rules_run": len(results),
        "rules_with_findings": [r.rule.id for r in results if r.count],
        "errors": [r.rule.id for r in results if r.error],
        "details": [r.as_dict() for r in results if r.count or r.error],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="daily read-only consistency check")
    ap.add_argument("--rules", default=str(Path(__file__).with_name("rules.yaml")))
    ap.add_argument("--webhook", default=os.environ.get("CONSISTENCY_WEBHOOK_URL"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    url = os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/alpha")
    url = url.replace("postgresql+psycopg://", "postgresql://")
    rules = load_rules(args.rules)

    with psycopg.connect(url) as conn:
        results, findings = run_all(conn, rules)

    payload = summary(results, findings)
    if not args.quiet:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.webhook:
        payload["webhook_sent"] = send_webhook(args.webhook, payload)
        if not args.quiet:
            print("webhook_sent:", payload["webhook_sent"], file=sys.stderr)
    return 0 if findings == 0 and not payload["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
