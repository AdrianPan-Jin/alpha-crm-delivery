#!/usr/bin/env python3
"""track_event 按月分区：初始化 + 分区维护 + 异常时间戳告警。

对应任务：S3-TRK-002（月分区表与分区自动维护）
- 父表按 RANGE (occurred_at) 月分区，另有默认分区接住异常时间戳
- maintain：保证「当月 + 未来 N 月」的分区存在（幂等），并统计默认分区里的异常行
- 全部规则可用环境变量覆盖，不硬编码
"""
from __future__ import annotations

import argparse
import datetime as dt
import os

import psycopg

SCHEMA = os.environ.get("TE_SCHEMA", "tracking")
TABLE = os.environ.get("TE_TABLE", "track_event")
AHEAD = int(os.environ.get("TE_MONTHS_AHEAD", "2"))

PARENT_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.{table} (
    id            bigserial,
    org_id        uuid        NOT NULL,
    event_name    text        NOT NULL,
    occurred_at   timestamptz NOT NULL,
    payload       jsonb       NOT NULL DEFAULT '{{}}'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE IF NOT EXISTS {schema}.{table}_default
    PARTITION OF {schema}.{table} DEFAULT;
"""

INDEX_DDL = """
CREATE INDEX IF NOT EXISTS ix_{table}_occurred ON {schema}.{table} (occurred_at);
CREATE INDEX IF NOT EXISTS ix_{table}_org_name ON {schema}.{table} (org_id, event_name, occurred_at DESC);
"""

INSPECT_DEFAULT = """
SELECT count(*) FROM {schema}.{table}_default;
"""


def month_bounds(d: dt.date) -> tuple[dt.date, dt.date]:
    start = d.replace(day=1)
    nxt = (start + dt.timedelta(days=32)).replace(day=1)
    return start, nxt


def partition_name(table: str, start: dt.date) -> str:
    return f"{table}_{start:%Y_%m}"


def ensure_partitions(conn: psycopg.Connection, today: dt.date | None = None, ahead: int = AHEAD,
                      schema: str = SCHEMA, table: str = TABLE) -> list[str]:
    """保证当月 + 未来 ahead 个月的分区存在；返回新建的分区名。"""
    today = today or dt.date.today()
    created: list[str] = []
    cursor = today
    for _ in range(ahead + 1):
        start, end = month_bounds(cursor)
        name = partition_name(table, start)
        exists = conn.execute(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relname = %s",
            (schema, name),
        ).fetchone()
        if not exists:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {schema}.{name} PARTITION OF {schema}.{table} "
                f"FOR VALUES FROM ('{start}') TO ('{end}')"
            )
            created.append(name)
        cursor = end
    return created


def alerts(conn: psycopg.Connection, threshold: int = 0, schema: str = SCHEMA, table: str = TABLE) -> list[dict]:
    """默认分区里落了多少异常行；超过阈值即告警。"""
    total = conn.execute(INSPECT_DEFAULT.format(schema=schema, table=table)).fetchone()[0]
    if total <= threshold:
        return []
    rows = conn.execute(
        f"SELECT min(occurred_at), max(occurred_at), count(*) FROM {schema}.{table}_default"
    ).fetchone()
    return [{
        "alert": "events_outside_partition_range",
        "rows_in_default": total,
        "min_occurred_at": rows[0].isoformat() if rows[0] else None,
        "max_occurred_at": rows[1].isoformat() if rows[1] else None,
    }]


def init(conn: psycopg.Connection, schema: str = SCHEMA, table: str = TABLE) -> None:
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    conn.execute(PARENT_DDL.format(schema=schema, table=table))
    conn.execute(INDEX_DDL.format(schema=schema, table=table))
    ensure_partitions(conn, schema=schema, table=table)


def drop(conn: psycopg.Connection, schema: str = SCHEMA) -> None:
    conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def main() -> None:
    ap = argparse.ArgumentParser(description="track_event 月分区维护")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:55433/alpha_part"))
    ap.add_argument("--init", action="store_true", help="建 schema + 父表 + 默认分区 + 索引 + 当月分区")
    ap.add_argument("--drop", action="store_true", help="删整个 schema（仅限本地/测试库）")
    ap.add_argument("--ahead", type=int, default=AHEAD)
    ap.add_argument("--dry-run", action="store_true", help="只报告将创建的分区，不落库")
    ap.add_argument("--alert-threshold", type=int, default=0)
    args = ap.parse_args()

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        if args.drop:
            drop(conn)
            print({"dropped": SCHEMA})
            return
        if args.init:
            init(conn)
        created = [] if args.dry_run else ensure_partitions(conn, ahead=args.ahead)
        parts = conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relname LIKE %s ORDER BY c.relname",
            (SCHEMA, f"{TABLE}_2%"),
        ).fetchall()
        print({
            "created": created,
            "partitions": [p[0] for p in parts],
            "alerts": alerts(conn, args.alert_threshold),
        })


if __name__ == "__main__":
    main()
