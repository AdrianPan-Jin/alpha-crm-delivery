"""种子数据：1 条规则 + 1 个已发布版本 + 12 条规则条目（幂等）。

AC4：导入后 `quote_rule_item` 恰好 12 行；重复导入仍是 12 行。

用法：
  DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55432/qr_demo \
  python scripts/seed_quote_rules.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import uuid

import psycopg

ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")
RULE_CODE = "QR-DEFAULT"

ITEMS = [
    ("会员年费（标准）", 1_280_000, 1, 0),
    ("会员年费（银卡）", 2_980_000, 1, 0),
    ("会员年费（金卡）", 6_880_000, 1, 500),        # 5% 折扣（basis points）
    ("资源对接服务费", 300_000, 1, 0),
    ("线下活动席位", 120_000, 1, 0),
    ("企业走访组织费", 480_000, 1, 0),
    ("会员名录入册", 88_000, 1, 0),
    ("定制化数据报表", 260_000, 1, 0),
    ("专属客户经理（季度）", 900_000, 1, 0),
    ("品牌露出（季度）", 1_500_000, 1, 0),
    ("招商引荐佣金", 5_000_000, 1, 0),
    ("增值培训（每场）", 350_000, 1, 0),
]


def dsn() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/qr_demo")
    return url.replace("postgresql+psycopg://", "postgresql://")


def main() -> int:
    today = dt.date.today()
    with psycopg.connect(dsn(), autocommit=True) as conn:
        rule_id = conn.execute(
            """
            INSERT INTO quote_rule (org_id, code, name, currency, status)
            VALUES (%s, %s, %s, 'CNY', 'published')
            ON CONFLICT (org_id, code) WHERE deleted_at IS NULL
            DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (ORG, RULE_CODE, "默认报价规则"),
        ).fetchone()[0]

        version_id = conn.execute(
            """
            INSERT INTO quote_rule_version
                (org_id, rule_id, version_no, status, valid_from, valid_to, note)
            VALUES (%s, %s, 1, 'published', %s, NULL, '初始版本')
            ON CONFLICT (rule_id, version_no) DO UPDATE SET note = EXCLUDED.note
            RETURNING id
            """,
            (ORG, rule_id, today),
        ).fetchone()[0]

        for seq, (name, cents, min_qty, discount_bp) in enumerate(ITEMS, start=1):
            conn.execute(
                """
                INSERT INTO quote_rule_item
                    (org_id, version_id, member_company_id, seq_no, item_name,
                     unit_price_cents, min_qty, discount_bp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (version_id, seq_no) DO UPDATE
                   SET item_name = EXCLUDED.item_name,
                       unit_price_cents = EXCLUDED.unit_price_cents,
                       min_qty = EXCLUDED.min_qty,
                       discount_bp = EXCLUDED.discount_bp
                """,
                (ORG, version_id, ORG, seq, name, cents, min_qty, discount_bp),
            )

        total = conn.execute("SELECT count(*) FROM quote_rule_item").fetchone()[0]
        print(f"seeded: rule={rule_id} version={version_id} items={total}")
        return 0 if total == 12 else 1


if __name__ == "__main__":
    sys.exit(main())
