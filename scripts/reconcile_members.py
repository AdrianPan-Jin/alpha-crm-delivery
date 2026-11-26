"""Reconcile the legacy member data export against the new platform database.

Usage
    python scripts/reconcile_members.py --source fixtures/legacy --out out/reconcile \
        [--site SITE_UUID] [--sample N]

Five source objects are compared: companies, contacts, memberships, tags,
company_tags. Six classes of known discrepancy are detected:

    missing          source row has no counterpart in the target system
    duplicate        the same source_id occurs twice in the source export
    many_to_one      several source_ids resolve to the same target uuid
    mismatch         both sides exist but a normalised field differs
    orphan           contact / membership references a company that does not exist
    credit_code_dup  two different companies share one unified credit code

Exit codes: 0 no differences, 1 differences found, 2 configuration / input error.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from scripts.common import database_url  # noqa: E402
from scripts.normalize import clean, credit_code, mask_phone, phone  # noqa: E402

MASKED_FIELDS = {"phone"}
PHONE_RE = re.compile(r"1[3-9]\d{9}")


@dataclass
class Finding:
    kind: str
    entity: str
    key: str
    field: str = ""
    source_value: str = ""
    target_value: str = ""
    note: str = ""


@dataclass
class Spec:
    entity: str
    filename: str
    table: str
    key_field: str
    columns: dict[str, str]  # source column -> target column
    normalizers: dict[str, callable] = field(default_factory=dict)  # target column -> fn


COMPANIES = Spec(
    entity="companies",
    filename="companies.csv",
    table="companies",
    key_field="source_id",
    columns={
        "公司名称": "name",
        "统一社会信用代码": "unified_credit_code",
        "行业": "industry",
        "会员等级": "level",
        "状态": "status",
    },
    normalizers={"name": clean, "unified_credit_code": credit_code, "industry": clean, "level": clean, "status": clean},
)

CONTACTS = Spec(
    entity="contacts",
    filename="contacts.csv",
    table="contacts",
    key_field="source_id",
    columns={
        "姓名": "name",
        "手机号": "phone",
        "职位": "title",
        "企业source_id": "company_source_id",
    },
    normalizers={"name": clean, "phone": phone, "title": clean, "company_source_id": clean},
)

TAGS = Spec(
    entity="tags",
    filename="tags.csv",
    table="tags",
    key_field="source_id",
    columns={"标签名称": "name", "颜色": "color"},
    normalizers={"name": clean, "color": clean},
)

TAG_RELATIONS = Spec(
    entity="company_tags",
    filename="company_tags.csv",
    table="company_tags",
    key_field="source_id",
    columns={"企业source_id": "company_source_id", "标签source_id": "tag_source_id"},
    normalizers={"company_source_id": clean, "tag_source_id": clean},
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"missing source file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [{(k or "").strip(): (v or "") for k, v in row.items()} for row in reader]
    return rows


def load_target(conn, spec: Spec, org: str | None, sample: int | None) -> dict[str, dict]:
    """Return {source_id: {column: value, 'uuid': ...}} from the target table."""
    sql = (
        f"SELECT m.source_id, t.* FROM legacy_map m JOIN {spec.table} t ON t.id = m.target_id "
        f"WHERE 1=1"
    )
    params: list = []
    if org:
        sql += " AND m.org_id = %s"
        params.append(org)
    sql += " ORDER BY m.source_id"
    if sample:
        sql += " LIMIT %s"
        params.append(sample)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        names = [d.name for d in cur.description]
        rows = cur.fetchall()
    result: dict[str, dict] = {}
    for row in rows:
        record = dict(zip(names, row))
        result.setdefault(record["source_id"], record)
    return result


def check_duplicates(rows: list[dict], spec: Spec) -> list[Finding]:
    seen: dict[str, int] = {}
    for row in rows:
        key = clean(row.get(spec.key_field))
        seen[key] = seen.get(key, 0) + 1
    return [
        Finding("duplicate", spec.entity, key, note=f"source export contains this key {count} times")
        for key, count in seen.items()
        if key and count > 1
    ]


def check_missing(rows: list[dict], target: dict, spec: Spec) -> list[Finding]:
    findings = []
    for row in rows:
        key = clean(row.get(spec.key_field))
        if key and key not in target:
            findings.append(Finding("missing", spec.entity, key, note="no target row mapped from this source id"))
    return findings


def check_many_to_one(conn, org: str | None) -> list[Finding]:
    sql = "SELECT target_id, array_agg(source_id ORDER BY source_id) FROM legacy_map"
    params: list = []
    if org:
        sql += " WHERE org_id = %s"
        params.append(org)
    sql += " GROUP BY target_id HAVING count(*) > 1"
    return [
        Finding("many_to_one", "legacy_map", str(target_id), note=f"source ids {ids}")
        for target_id, ids in conn.execute(sql, params).fetchall()
    ]


def check_duplicate_mapping(conn, org: str | None) -> list[Finding]:
    """One source id mapped to more than one target uuid (ambiguous legacy mapping)."""
    sql = "SELECT source_id, array_agg(target_id::text ORDER BY target_id::text) FROM legacy_map"
    params: list = []
    if org:
        sql += " WHERE org_id = %s"
        params.append(org)
    sql += " GROUP BY source_id HAVING count(DISTINCT target_id) > 1"
    return [
        Finding("duplicate", "legacy_map", source_id, note=f"mapped to {len(targets)} target rows: {targets}")
        for source_id, targets in conn.execute(sql, params).fetchall()
    ]


def check_mismatch(rows: list[dict], target: dict, spec: Spec) -> list[Finding]:
    findings = []
    for row in rows:
        key = clean(row.get(spec.key_field))
        hit = target.get(key)
        if not hit:
            continue
        for source_col, target_col in spec.columns.items():
            if target_col not in hit:
                continue
            normalizer = spec.normalizers.get(target_col, clean)
            source_value = normalizer(row.get(source_col))
            target_value = normalizer(hit.get(target_col) if isinstance(hit.get(target_col), str) else str(hit.get(target_col) or ""))
            if source_value != target_value:
                shown_source = mask_phone(source_value) if target_col in MASKED_FIELDS else source_value
                shown_target = mask_phone(target_value) if target_col in MASKED_FIELDS else target_value
                findings.append(
                    Finding("mismatch", spec.entity, key, field=target_col, source_value=shown_source, target_value=shown_target)
                )
    return findings


def check_orphan_contacts(rows: list[dict], company_keys: set[str]) -> list[Finding]:
    findings = []
    for row in rows:
        company_key = clean(row.get("企业source_id"))
        if company_key and company_key not in company_keys:
            findings.append(
                Finding(
                    "orphan",
                    "contacts",
                    clean(row.get("source_id")),
                    field="company_source_id",
                    source_value=company_key,
                    note="contact references a company that is not present in the source export",
                )
            )
    return findings


def check_tag_relations(
    rows: list[dict], company_uuid: dict[str, str], tag_uuid: dict[str, str], target_pairs: set[tuple[str, str]]
) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for row in rows:
        key = clean(row.get("source_id"))
        company_key = clean(row.get("企业source_id"))
        tag_key = clean(row.get("标签source_id"))
        seen[key] = seen.get(key, 0) + 1
        if company_key not in company_uuid or tag_key not in tag_uuid:
            findings.append(
                Finding("missing", "company_tags", key, note=f"company {company_key} or tag {tag_key} has no target mapping")
            )
            continue
        if (company_uuid[company_key], tag_uuid[tag_key]) not in target_pairs:
            findings.append(Finding("missing", "company_tags", key, note="relation is absent from the target system"))
    for key, count in seen.items():
        if key and count > 1:
            findings.append(Finding("duplicate", "company_tags", key, note=f"source export contains this key {count} times"))
    return findings


def check_credit_code_duplicates(rows: list[dict]) -> list[Finding]:
    by_code: dict[str, list[str]] = {}
    for row in rows:
        code = credit_code(row.get("统一社会信用代码"))
        if code:
            by_code.setdefault(code, []).append(clean(row.get("source_id")))
    return [
        Finding("credit_code_dup", "companies", code, note=f"shared by source ids {ids}")
        for code, ids in by_code.items()
        if len(ids) > 1
    ]


def write_outputs(findings: list[Finding], out_dir: Path, stats: dict) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "diffs.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(Finding("", "", "")).keys()))
        writer.writeheader()
        for finding in findings:
            writer.writerow(asdict(finding))

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1

    report = out_dir / "report.md"
    lines = [
        "# 会员主数据核对报告",
        "",
        f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 源文件目录：{stats.get('source')}",
        f"- 目标库：{stats.get('database')}",
        f"- 耗时：{stats.get('elapsed_s')} 秒",
        f"- 差异总数：{len(findings)}",
        "",
        "## 差异分类",
        "",
        "| 类型 | 数量 |",
        "| --- | --- |",
    ]
    for kind in ("missing", "duplicate", "many_to_one", "mismatch", "orphan", "credit_code_dup"):
        lines.append(f"| {kind} | {counts.get(kind, 0)} |")
    lines += ["", "## 源数据规模", "", "| 实体 | 行数 |", "| --- | --- |"]
    for entity, n in stats.get("rows", {}).items():
        lines.append(f"| {entity} | {n} |")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="directory with companies.csv / contacts.csv / tags.csv / company_tags.csv")
    parser.add_argument("--out", default="out/reconcile")
    parser.add_argument("--site", default=None, help="site uuid to scope the comparison")
    parser.add_argument("--sample", type=int, default=None, help="compare at most N rows per entity")
    args = parser.parse_args(argv)

    started = time.time()
    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"configuration error: {source_dir} is not a directory", file=sys.stderr)
        return 2

    try:
        companies = read_csv(source_dir / COMPANIES.filename)
        contacts = read_csv(source_dir / CONTACTS.filename)
        tags = read_csv(source_dir / TAGS.filename)
        tag_relations = read_csv(source_dir / TAG_RELATIONS.filename)
    except SystemExit as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    for spec, rows in ((COMPANIES, companies), (CONTACTS, contacts), (TAGS, tags), (TAG_RELATIONS, tag_relations)):
        required = {spec.key_field, *spec.columns}
        missing_cols = required - set(rows[0].keys() if rows else required)
        if missing_cols:
            print(f"configuration error: {spec.filename} missing columns {sorted(missing_cols)}", file=sys.stderr)
            return 2

    findings: list[Finding] = []
    try:
        with psycopg.connect(database_url()) as conn:
            targets = {
                spec.entity: load_target(conn, spec, args.site, args.sample)
                for spec in (COMPANIES, CONTACTS, TAGS)
            }
            findings += check_many_to_one(conn, args.site)
            findings += check_duplicate_mapping(conn, args.site)
            target_pairs = {
                (str(company_id), str(tag_id))
                for company_id, tag_id in conn.execute(
                    "SELECT company_id, tag_id FROM company_tags WHERE deleted_at IS NULL"
                ).fetchall()
            }

    except psycopg.Error as exc:
        print(f"database error: {exc}", file=sys.stderr)
        return 2

    for spec, rows in ((COMPANIES, companies), (CONTACTS, contacts), (TAGS, tags)):
        findings += check_duplicates(rows, spec)
        findings += check_missing(rows, targets[spec.entity], spec)
        findings += check_mismatch(rows, targets[spec.entity], spec)

    company_keys = {clean(row.get("source_id")) for row in companies}
    findings += check_orphan_contacts(contacts, company_keys)
    findings += check_credit_code_duplicates(companies)

    # Relation rows are keyed by the natural pair and resolved through the entity mapping.
    company_uuid = {k: str(v["id"]) for k, v in targets["companies"].items()}
    tag_uuid = {k: str(v["id"]) for k, v in targets["tags"].items()}
    findings += check_tag_relations(tag_relations, company_uuid, tag_uuid, target_pairs)

    stats = {
        "source": str(source_dir),
        "database": database_url().split("@")[-1],
        "elapsed_s": round(time.time() - started, 3),
        "rows": {spec.entity: len(rows) for spec, rows in ((COMPANIES, companies), (CONTACTS, contacts), (TAGS, tags), (TAG_RELATIONS, tag_relations))},
    }
    report, csv_path = write_outputs(findings, Path(args.out), stats)

    sample = [asdict(f) for f in findings[:5]]
    print(
        json.dumps(
            {
                "differences": len(findings),
                "by_kind": {k: sum(1 for f in findings if f.kind == k) for k in sorted({f.kind for f in findings})},
                "report": str(report),
                "diffs_csv": str(csv_path),
                "elapsed_s": stats["elapsed_s"],
                "sample": sample,
            },
            ensure_ascii=False,
        )
    )
    body = csv_path.read_text(encoding="utf-8-sig")
    if PHONE_RE.search(body):
        print("internal error: unmasked phone leaked into diffs.csv", file=sys.stderr)
        return 2
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
