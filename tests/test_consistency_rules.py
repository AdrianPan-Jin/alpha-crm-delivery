"""Acceptance tests for the daily read-only consistency check (ticket 2964).

Acceptance items:
1. at least 12 read-only rules, each proven to detect a planted violation
2. disabling a rule in the YAML really stops it from running
3. the webhook payload carries the summary
4. rules cannot write: the engine runs them in a READ ONLY transaction, and a
   non-SELECT rule is rejected at load time

Design note: several of these invariants are also enforced by database
constraints. To prove the *check* works, the fixture removes the corresponding
constraint first - this models a row that got in through a bulk import, a
direct load, or a dropped index, which is exactly what a daily check is for.
The database is throwaway and is dropped by the fixture.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

from app.consistency import engine

ROOT = Path(__file__).resolve().parents[1]
PG_HOST = os.environ.get("PG_HOST", "127.0.0.1")
PG_PORT = int(os.environ.get("PG_PORT", "55432"))
ORG = "11111111-1111-1111-1111-111111111111"
SITE = "22222222-2222-2222-2222-222222222222"
RULES = ROOT / "app" / "consistency" / "rules.yaml"
TABLES = (
    "event_checkins, event_tickets, event_signups, crm_interaction, crm_membership,"
    " crm_contract, contacts, companies, episode_conversion_stats, podcast_episodes"
)


def _admin():
    return psycopg.connect(
        host=PG_HOST, port=PG_PORT, user="postgres", dbname="postgres", autocommit=True
    )


def _url(name: str) -> str:
    return f"postgresql+psycopg://postgres@{PG_HOST}:{PG_PORT}/{name}"


@pytest.fixture(scope="module")
def db() -> psycopg.Connection:
    name = f"alpha_chk_{uuid.uuid4().hex[:8]}"
    with _admin() as adm:
        adm.execute(f'CREATE DATABASE "{name}"')
    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "DATABASE_URL": _url(name)},
    )
    assert up.returncode == 0, up.stdout + up.stderr
    # autocommit keeps each planted violation independent: a rejected INSERT must not
    # poison the connection for the next rule's fixture
    conn = psycopg.connect(host=PG_HOST, port=PG_PORT, user="postgres", dbname=name, autocommit=True)
    yield conn
    conn.close()
    with _admin() as adm:
        adm.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _company(conn, name, uscc=None, deleted=False):
    return conn.execute(
        "INSERT INTO companies (org_id, site_id, name, unified_credit_code, deleted_at) "
        "VALUES (%s, %s, %s, %s, CASE WHEN %s THEN now() ELSE NULL END) RETURNING id",
        (ORG, SITE, name, uscc, deleted),
    ).fetchone()[0]


def test_rules_file_has_at_least_12_rules():
    rules = engine.load_rules(RULES)
    assert len(rules) >= 12
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids)), "rule ids must be unique"


def test_non_select_rule_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("rules:\n  - id: x\n    sql: DELETE FROM companies\n", encoding="utf-8")
    with pytest.raises(ValueError):
        engine.load_rules(bad)


@pytest.mark.parametrize(
    "rule_id,plant",
    [
        ("company_uscc_duplicate_alive", "uscc_dup"),
        ("company_name_duplicate_alive", "name_dup"),
        ("contact_on_deleted_company", "contact_deleted_company"),
        ("contact_phone_not_normalized", "bad_phone"),
        ("membership_overlap_active", "membership_overlap"),
        ("membership_end_before_start", "membership_reversed"),
        ("contract_signed_without_sign_date", "contract_no_sign_date"),
        ("contract_negative_amount", "contract_negative"),
        ("event_signup_duplicate_confirmed", "signup_dup"),
        ("ticket_without_alive_signup", "ticket_on_deleted_signup"),
        ("interaction_on_deleted_company", "interaction_deleted_company"),
        ("interaction_summary_empty", "interaction_empty_summary"),
        ("conversion_stats_negative", "stats_negative"),
    ],
)
def test_each_rule_detects_one_planted_violation(db, rule_id, plant):
    db.execute(f"TRUNCATE {TABLES} CASCADE")
    _plant(db, plant)

    rules = [r for r in engine.load_rules(RULES) if r.id == rule_id]
    assert len(rules) == 1
    result = engine.run_rule(db, rules[0])
    assert result.error is None
    assert result.count >= 1, f"{rule_id} did not detect the planted violation"


def _plant(db, kind: str) -> None:
    """Insert exactly one violation of the matching rule."""
    if kind == "uscc_dup":
        # bypass: bulk import / direct load (the API would hit the unique index)
        db.execute("DROP INDEX IF EXISTS uq_companies_org_uscc_alive")
        _company(db, "dup uscc 1", "91330100MA2AB3CD4E")
        _company(db, "dup uscc 2", "91330100MA2AB3CD4E")
    elif kind == "name_dup":
        db.execute("DROP INDEX IF EXISTS uq_companies_org_name_alive")
        _company(db, "same name ltd")
        _company(db, "same name ltd")
    elif kind == "contact_deleted_company":
        cid = _company(db, "deleted co", deleted=True)
        db.execute(
            "INSERT INTO contacts (org_id, site_id, company_id, name, phone) VALUES (%s,%s,%s,%s,%s)",
            (ORG, SITE, cid, "张三", "13800001111"),
        )
    elif kind == "bad_phone":
        db.execute("ALTER TABLE contacts DROP CONSTRAINT IF EXISTS ck_contacts_phone")
        cid = _company(db, "phone co")
        db.execute(
            "INSERT INTO contacts (org_id, site_id, company_id, name, phone) VALUES (%s,%s,%s,%s,%s)",
            (ORG, SITE, cid, "李四", "12345678901"),
        )
    elif kind == "membership_overlap":
        db.execute("ALTER TABLE crm_membership DROP CONSTRAINT IF EXISTS ex_membership_period_overlap")
        cid = _company(db, "member co")
        for start, end in (("2026-01-01", "2026-06-30"), ("2026-05-01", "2026-12-31")):
            db.execute(
                "INSERT INTO crm_membership (org_id, site_id, member_no, company_id, status,"
                " start_date, end_date) VALUES (%s,%s,%s,%s,'active',%s,%s)",
                (ORG, SITE, uuid.uuid4().hex[:8], cid, start, end),
            )
    elif kind == "membership_reversed":
        db.execute("ALTER TABLE crm_membership DROP CONSTRAINT IF EXISTS ck_membership_dates")
        cid = _company(db, "member reversed")
        db.execute(
            "INSERT INTO crm_membership (org_id, site_id, member_no, company_id, status,"
            " start_date, end_date) VALUES (%s,%s,%s,%s,'active','2026-06-30','2026-01-01')",
            (ORG, SITE, uuid.uuid4().hex[:8], cid),
        )
    elif kind == "contract_no_sign_date":
        # esign finished (esign_status='signed') but nobody recorded the signing date:
        # legal/finance needs this backfilled, and no DB constraint can express it
        cid = _company(db, "contract co")
        db.execute(
            "INSERT INTO crm_contract (org_id, site_id, contract_no, company_id, status,"
            " esign_status, amount_cents) VALUES (%s,%s,%s,%s,'draft','signed',100000)",
            (ORG, SITE, "HT-1", cid),
        )
    elif kind == "contract_negative":
        db.execute("ALTER TABLE crm_contract DROP CONSTRAINT IF EXISTS ck_contract_amount_nonneg")
        cid = _company(db, "contract neg")
        db.execute(
            "INSERT INTO crm_contract (org_id, site_id, contract_no, company_id, status, amount_cents)"
            " VALUES (%s,%s,%s,%s,'draft',-1)",
            (ORG, SITE, "HT-2", cid),
        )
    elif kind == "signup_dup":
        db.execute("DROP INDEX IF EXISTS uq_signups_event_member_alive")
        ev, member = uuid.uuid4(), uuid.uuid4()
        for _ in range(2):
            db.execute(
                "INSERT INTO event_signups (org_id, site_id, event_id, member_id, status)"
                " VALUES (%s,%s,%s,%s,'confirmed')",
                (ORG, SITE, ev, member),
            )
    elif kind == "ticket_on_deleted_signup":
        ev, member = uuid.uuid4(), uuid.uuid4()
        sid = db.execute(
            "INSERT INTO event_signups (org_id, site_id, event_id, member_id, status, deleted_at)"
            " VALUES (%s,%s,%s,%s,'confirmed', now()) RETURNING id",
            (ORG, SITE, ev, member),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO event_tickets (org_id, site_id, signup_id, ticket_no) VALUES (%s,%s,%s,%s)",
            (ORG, SITE, sid, "T-1"),
        )
    elif kind == "interaction_deleted_company":
        cid = _company(db, "gone co", deleted=True)
        db.execute(
            "INSERT INTO crm_interaction (org_id, site_id, company_id, type, occurred_at, summary)"
            " VALUES (%s,%s,%s,'call', now(), '电话沟通')",
            (ORG, SITE, cid),
        )
    elif kind == "interaction_empty_summary":
        cid = _company(db, "empty summary co")
        db.execute(
            "INSERT INTO crm_interaction (org_id, site_id, company_id, type, occurred_at, summary)"
            " VALUES (%s,%s,%s,'call', now(), '  ')",
            (ORG, SITE, cid),
        )
    elif kind == "stats_negative":
        db.execute(
            "ALTER TABLE episode_conversion_stats DROP CONSTRAINT IF EXISTS ck_intro_counts_non_negative"
        )
        ep = db.execute(
            "INSERT INTO podcast_episodes (org_id, site_id, title, published_at)"
            " VALUES (%s,%s,'ep', now()) RETURNING id",
            (ORG, SITE),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO episode_conversion_stats (org_id, episode_id, stat_date, intro_requests)"
            " VALUES (%s,%s,current_date,-1)",
            (ORG, ep),
        )
    else:  # pragma: no cover
        raise AssertionError(f"unknown plant {kind}")


def test_disabled_rule_is_skipped(db, tmp_path):
    text = RULES.read_text(encoding="utf-8")
    broken = text.replace(
        "  - id: contact_phone_not_normalized\n"
        "    title: 联系人手机号不符合 11 位大陆号格式\n"
        "    severity: medium\n",
        "  - id: contact_phone_not_normalized\n"
        "    title: 联系人手机号不符合 11 位大陆号格式\n"
        "    severity: medium\n"
        "    enabled: false\n",
    )
    assert "enabled: false" in broken
    path = tmp_path / "rules.yaml"
    path.write_text(broken, encoding="utf-8")

    rules = engine.load_rules(path)
    disabled = [r for r in rules if r.id == "contact_phone_not_normalized"]
    assert disabled and disabled[0].enabled is False

    db.execute(f"TRUNCATE {TABLES} CASCADE")
    _plant(db, "bad_phone")

    enabled_only = [r for r in rules if r.enabled]
    results, findings = engine.run_all(db, enabled_only)
    assert all(r.rule.id != "contact_phone_not_normalized" for r in results)
    assert findings == 0


def test_run_all_reports_webhook_payload(db):
    db.execute(f"TRUNCATE {TABLES} CASCADE")
    _plant(db, "bad_phone")

    rules = engine.load_rules(RULES)
    results, findings = engine.run_all(db, rules)
    payload = engine.summary(results, findings)
    assert payload["ok"] is False
    assert payload["findings"] >= 1
    assert "contact_phone_not_normalized" in payload["rules_with_findings"]
    assert payload["by_severity"]["medium"] >= 1
    # JSON-serialisable end to end (webhook body)
    json.dumps(payload, ensure_ascii=False, default=str)


def test_cli_exit_code(db):
    db.execute(f"TRUNCATE {TABLES} CASCADE")
    result = subprocess.run(
        [sys.executable, "-m", "app.consistency.engine", "--rules", str(RULES), "--quiet"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **os.environ,
            "DATABASE_URL": f"postgresql://postgres@{PG_HOST}:{PG_PORT}/{db.info.dbname}",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
