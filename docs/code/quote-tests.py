"""AC2：已发布版本有效期互斥；相邻区间允许；草稿/软删不参与互斥。"""
from __future__ import annotations

import datetime as dt
import uuid

import psycopg
import pytest

pytestmark = pytest.mark.skipif(
    not __import__("psycopg").connect(
        port=int(__import__("os").environ.get("PG_PORT", "55432")),
        host=__import__("os").environ.get("PG_HOST", "127.0.0.1"),
        user="postgres", dbname="postgres", autocommit=True
    ).execute("SELECT 1 FROM pg_available_extensions WHERE name='btree_gist'").fetchone(),
    reason="btree_gist not available",
)

ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _rule(conn) -> uuid.UUID:
    return conn.execute(
        "INSERT INTO quote_rule (org_id, code, name) VALUES (%s, %s, '规则') RETURNING id",
        (ORG, f"QR-{uuid.uuid4().hex[:6]}"),
    ).fetchone()[0]


def _version(conn, rule_id, start: dt.date, end: dt.date | None, status="published"):
    return conn.execute(
        """INSERT INTO quote_rule_version (org_id, rule_id, version_no, status, valid_from, valid_to)
           VALUES (%s, %s, (SELECT coalesce(max(version_no),0)+1 FROM quote_rule_version WHERE rule_id=%s),
                   %s, %s, %s) RETURNING id""",
        (ORG, rule_id, rule_id, status, start, end),
    ).fetchone()[0]


def test_published_versions_cannot_overlap(db):
    rule = _rule(db)
    _version(db, rule, dt.date(2026, 1, 1), dt.date(2026, 7, 1))
    with db.transaction():
        with pytest.raises(psycopg.errors.ExclusionViolation):
            _version(db, rule, dt.date(2026, 6, 30), dt.date(2026, 12, 31))


def test_adjacent_versions_allowed(db):
    rule = _rule(db)
    _version(db, rule, dt.date(2026, 1, 1), dt.date(2026, 7, 1))
    # [) 左闭右开：7-1 开始的版本与 7-1 结束的上一个版本相接，不算重叠
    _version(db, rule, dt.date(2026, 7, 1), dt.date(2026, 12, 31))


def test_draft_and_soft_deleted_are_excluded(db):
    rule = _rule(db)
    _version(db, rule, dt.date(2026, 1, 1), dt.date(2026, 7, 1), status="draft")
    _version(db, rule, dt.date(2026, 1, 1), dt.date(2026, 7, 1), status="published")
    db.execute("UPDATE quote_rule_version SET deleted_at = now() WHERE status='published' AND rule_id=%s", (rule,))
    _version(db, rule, dt.date(2026, 2, 1), dt.date(2026, 6, 1), status="published")
