from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent
ORG = "11111111-1111-1111-1111-111111111111"
PHONE_RE = re.compile(r"1[3-9]\d{9}")


def run(script: str, *args: str, db_url: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": db_url, "PYTHONIOENCODING": "utf-8", **(env_extra or {})}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def load_fixtures(db_url: str, root: Path) -> None:
    result = run("make_fixtures.py", "--root", str(root), "--load-target", "--org", ORG, db_url=db_url)
    assert result.returncode == 0, result.stderr


def add_stale_mapping(db_url: str) -> None:
    """C900 -> the same uuid as C001, producing the many-to-one class."""
    raw = db_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw) as conn:
        conn.execute(
            "INSERT INTO legacy_map (org_id, entity, source_id, target_id) "
            "SELECT %s, 'companies', 'C900', m.target_id FROM legacy_map m WHERE m.source_id = 'C001'",
            (ORG,),
        )
        conn.commit()


def reconcile(db_url: str, source: Path, out: Path) -> subprocess.CompletedProcess:
    return run("reconcile_members.py", "--source", str(source), "--out", str(out), db_url=db_url)


def read_diffs(out: Path) -> list[dict]:
    with (out / "diffs.csv").open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def fixtures_root(rc_db: str, tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("fixtures")
    load_fixtures(rc_db, root)
    return root


def test_clean_dataset_has_no_differences(rc_db, fixtures_root):
    out = fixtures_root / "out-clean"
    result = reconcile(rc_db, fixtures_root / "clean", out)
    assert result.returncode == 0, result.stderr
    assert read_diffs(out) == []


def test_dirty_dataset_reports_six_classes_and_masks_phones(rc_db, fixtures_root):
    add_stale_mapping(rc_db)
    out = fixtures_root / "out-dirty"
    result = reconcile(rc_db, fixtures_root / "dirty", out)
    assert result.returncode == 1, result.stderr
    diffs = read_diffs(out)
    kinds = {row["kind"] for row in diffs}
    assert kinds == {"missing", "duplicate", "many_to_one", "mismatch", "orphan", "credit_code_dup"}
    assert PHONE_RE.search((out / "diffs.csv").read_text(encoding="utf-8-sig")) is None
    phone_rows = [row for row in diffs if row["field"] == "phone"]
    assert phone_rows and all(re.fullmatch(r"1\d{2}\*{4}\d{4}", row["source_value"]) for row in phone_rows)


def test_missing_source_column_exits_2(rc_db, fixtures_root, tmp_path):
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "companies.csv").write_text("source_id\nC1\n", encoding="utf-8")
    result = reconcile(rc_db, broken, tmp_path / "out-broken")
    assert result.returncode == 2
    assert "configuration error" in result.stderr


def test_performance_1000_companies_5000_contacts(rc_db, tmp_path):
    companies = [["C%04d" % i, f"测试企业{i}有限公司", f"91330100MA{i:07d}X", "软件和信息技术服务业", "normal", "active"] for i in range(1000)]
    contacts = [
        ["K%05d" % i, f"联系人{i}", f"138{i:08d}", "经理", f"C{i % 1000:04d}"]
        for i in range(5000)
    ]
    source = tmp_path / "perf"
    source.mkdir()
    for name, header, rows in (
        ("companies.csv", ["source_id", "公司名称", "统一社会信用代码", "行业", "会员等级", "状态"], companies),
        ("contacts.csv", ["source_id", "姓名", "手机号", "职位", "企业source_id"], contacts),
        ("tags.csv", ["source_id", "标签名称", "颜色"], [["T1", "重点", "#000"]]),
        ("company_tags.csv", ["source_id", "企业source_id", "标签source_id"], [["R1", "C0001", "T1"]]),
    ):
        with (source / name).open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)

    raw = rc_db.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw) as conn:
        conn.execute("DELETE FROM company_tags")
        conn.execute("DELETE FROM legacy_map")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM tags")
        conn.execute("DELETE FROM companies")
        ids = {}
        with conn.cursor() as cur:
            for r in companies:
                cur.execute(
                    "INSERT INTO companies (org_id, name, unified_credit_code, industry, level, status, external_key) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (ORG, r[1], r[2], r[3], r[4], r[5], r[0]),
                )
                ids[r[0]] = str(cur.fetchone()[0])
            for r in contacts:
                cur.execute(
                    "INSERT INTO contacts (org_id, company_id, name, phone, title) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (ORG, ids[r[4]], r[1], r[2], r[3]),
                )
                contact_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO legacy_map (org_id, entity, source_id, target_id) VALUES (%s, 'contacts', %s, %s)",
                    (ORG, r[0], contact_id),
                )
            cur.execute(
                "INSERT INTO tags (org_id, name, color) VALUES (%s, %s, %s) RETURNING id", (ORG, "重点", "#000")
            )
            tag_id = str(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO company_tags (company_id, tag_id) VALUES (%s, %s)", (ids["C0001"], tag_id)
            )
            cur.executemany(
                "INSERT INTO legacy_map (org_id, entity, source_id, target_id) VALUES (%s, 'companies', %s, %s)",
                [(ORG, key, uuid) for key, uuid in ids.items()],
            )
            cur.execute(
                "INSERT INTO legacy_map (org_id, entity, source_id, target_id) VALUES (%s, 'tags', 'T1', %s)",
                (ORG, tag_id),
            )
        conn.commit()

    started = time.time()
    result = reconcile(rc_db, source, tmp_path / "out-perf")
    elapsed = time.time() - started
    assert result.returncode == 0, result.stderr
    assert elapsed < 120, f"reconciliation took {elapsed:.1f}s"
    print(f"perf: 1000 companies / 5000 contacts reconciled in {elapsed:.2f}s")
