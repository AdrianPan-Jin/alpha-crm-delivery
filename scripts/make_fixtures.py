"""Build two fixture datasets for the reconciliation script.

clean/  source export that agrees with the target database -> expect 0 differences
dirty/  source export with all six known discrepancy classes

With --load-target the clean dataset is also written into DATABASE_URL as the
"new system" (normalised rows plus the legacy id mapping), so that running the
reconciliation against dirty/ reports exactly the six classes.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from scripts.common import database_url  # noqa: E402

COMPANY_HEADER = ["source_id", "公司名称", "统一社会信用代码", "行业", "会员等级", "状态"]
CONTACT_HEADER = ["source_id", "姓名", "手机号", "职位", "企业source_id"]
TAG_HEADER = ["source_id", "标签名称", "颜色"]
TAG_RELATION_HEADER = ["source_id", "企业source_id", "标签source_id"]

CLEAN_COMPANIES = [
    ["C001", "杭州云帆科技有限公司", "91330100MA2H8K7X1A", "软件和信息技术服务业", "gold", "active"],
    ["C002", "上海禾木供应链有限公司", "91310115MA1K4R2T3B", "批发业", "normal", "active"],
    ["C003", "深圳前海数智科技有限公司", "91440300MA5F7Y6Q2C", "软件和信息技术服务业", "platinum", "active"],
]
CLEAN_CONTACTS = [
    ["K001", "张伟", "13800138000", "总经理", "C001"],
    ["K002", "李娜", "+8613900139001", "采购总监", "C002"],
    ["K003", "王强", "13700137002", "技术负责人", "C003"],
]
CLEAN_TAGS = [["T001", "重点客户", "#f5222d"], ["T002", "待回访", "#faad14"]]
CLEAN_TAG_RELATIONS = [["R001", "C001", "T001"], ["R002", "C002", "T002"]]


def dirty_dataset() -> dict[str, list[list[str]]]:
    companies = [row[:] for row in CLEAN_COMPANIES]
    companies[0][1] = "杭州云帆科技有限公司（更名）"      # mismatch: name
    companies[0][2] = "91310115MA1K4R2T3B"              # credit_code_dup with C002
    companies[1][4] = "vip"                              # mismatch: level
    companies.append(["C004", "北京天成医疗器械有限公司", "91110108MA01J3S8E", "批发业", "normal", "active"])  # missing

    contacts = [row[:] for row in CLEAN_CONTACTS]
    contacts[2][2] = "13700137003"                       # mismatch: phone
    contacts.append(["K004", "赵敏", "13500135000", "财务", "C999"])   # orphan
    contacts.append(["K001", "张伟", "13800138000", "总经理", "C001"])  # duplicate source id
    return {
        "companies": companies,
        "contacts": contacts,
        "tags": [row[:] for row in CLEAN_TAGS],
        "company_tags": [row[:] for row in CLEAN_TAG_RELATIONS],
    }


def write_source(root: Path, rows: dict[str, list[list[str]]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for filename, header, name in (
        ("companies.csv", COMPANY_HEADER, "companies"),
        ("contacts.csv", CONTACT_HEADER, "contacts"),
        ("tags.csv", TAG_HEADER, "tags"),
        ("company_tags.csv", TAG_RELATION_HEADER, "company_tags"),
    ):
        with (root / filename).open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows[name])


def load_target(org: str) -> dict[str, str]:
    """Load the clean dataset as the migrated target system; return source_id -> uuid."""
    ids: dict[str, str] = {}
    with psycopg.connect(database_url()) as conn:
        conn.execute("DELETE FROM company_tags")
        conn.execute("DELETE FROM legacy_map")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM tags")
        conn.execute("DELETE FROM companies")

        for source_id, name, code, industry, level, status in CLEAN_COMPANIES:
            uuid = conn.execute(
                """
                INSERT INTO companies (org_id, name, unified_credit_code, industry, level, status)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (org, name, code, industry, level, status),
            ).fetchone()[0]
            ids[source_id] = str(uuid)

        for source_id, name, phone, title, company_source in CLEAN_CONTACTS:
            normalized = phone.replace("+86", "")
            uuid = conn.execute(
                "INSERT INTO contacts (org_id, company_id, name, phone, title) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (org, ids[company_source], name, normalized, title),
            ).fetchone()[0]
            ids[source_id] = str(uuid)

        for source_id, name, color in CLEAN_TAGS:
            ids[source_id] = str(
                conn.execute(
                    "INSERT INTO tags (org_id, name, color) VALUES (%s, %s, %s) RETURNING id",
                    (org, name, color),
                ).fetchone()[0]
            )

        for source_id, company_source, tag_source in CLEAN_TAG_RELATIONS:
            conn.execute(
                "INSERT INTO company_tags (company_id, tag_id) VALUES (%s, %s)",
                (ids[company_source], ids[tag_source]),
            )
            ids[source_id] = source_id

        for source_id, target in ids.items():
            if source_id.startswith("R"):
                continue  # relation rows have no uuid identity; the script derives them
            entity = {"C": "companies", "K": "contacts", "T": "tags"}[source_id[0]]
            conn.execute(
                "INSERT INTO legacy_map (org_id, entity, source_id, target_id) VALUES (%s, %s, %s, %s)",
                (org, entity, source_id, target),
            )
        conn.commit()
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="fixtures")
    parser.add_argument("--org", default="11111111-1111-1111-1111-111111111111")
    parser.add_argument("--load-target", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    write_source(root / "clean", {
        "companies": CLEAN_COMPANIES,
        "contacts": CLEAN_CONTACTS,
        "tags": CLEAN_TAGS,
        "company_tags": CLEAN_TAG_RELATIONS,
    })
    write_source(root / "dirty", dirty_dataset())
    print(f"clean fixtures: {root / 'clean'}")
    print(f"dirty fixtures: {root / 'dirty'}")

    if args.load_target:
        ids = load_target(args.org)
        print(f"target loaded: {len(ids)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
