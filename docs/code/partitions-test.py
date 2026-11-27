"""partition_kit 的验收测试（本地 PG19 实例，端口 55433）。

覆盖：
1. init 建出父表、默认分区、当月分区与索引
2. 写入本月事件落到当月分区（tableoid 断言），不落默认分区
3. 写入越界时间戳（去年）落到默认分区，alerts 报出
4. ensure_partitions 幂等：重复调用不再新建
5. ahead 参数生效：ahead 从 2 增到 4 时只多建两个月
6. drop 后 schema 不存在
"""
from __future__ import annotations

import datetime as dt
import os
import uuid

import psycopg
import pytest

import partition_kit as pk

PG = dict(host=os.environ.get("PG_HOST", "127.0.0.1"), port=int(os.environ.get("PG_PORT", "55433")),
          user="postgres")


@pytest.fixture(scope="module")
def db():
    name = "alpha_part_" + uuid.uuid4().hex[:6]
    with psycopg.connect(dbname="postgres", autocommit=True, **PG) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    with psycopg.connect(dbname=name, autocommit=True, **PG) as conn:
        yield conn
    with psycopg.connect(dbname="postgres", autocommit=True, **PG) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _partitions(db) -> set[str]:
    rows = db.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'tracking' AND c.relname LIKE 'track_event_2%' ORDER BY c.relname"
    ).fetchall()
    return {r[0] for r in rows}


def test_init_creates_parent_default_and_current_partition(db):
    pk.init(db)
    rows = db.execute(
        "SELECT c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'tracking' ORDER BY c.relname"
    ).fetchall()
    kinds = dict(rows)
    assert "track_event" in kinds
    assert "track_event_default" in kinds
    assert f"track_event_{dt.date.today():%Y_%m}" in kinds
    assert kinds["track_event"] == "p"  # 分区表


def test_row_routes_to_month_partition(db):
    pk.init(db)
    org = str(uuid.uuid4())
    now = dt.datetime.now(dt.timezone.utc)
    db.execute(
        "INSERT INTO tracking.track_event (org_id, event_name, occurred_at) VALUES (%s, %s, %s)",
        (org, "page_view", now),
    )
    part = db.execute(
        "SELECT tableoid::regclass::text FROM tracking.track_event WHERE org_id = %s", (org,)
    ).fetchone()[0]
    assert part == f"tracking.track_event_{now:%Y_%m}"
    assert pk.alerts(db) == []


def test_out_of_range_goes_to_default_and_alerts(db):
    pk.init(db)
    old = dt.datetime(2023, 5, 6, 12, 0, tzinfo=dt.timezone.utc)
    db.execute(
        "INSERT INTO tracking.track_event (org_id, event_name, occurred_at) VALUES (%s, %s, %s)",
        (str(uuid.uuid4()), "backfill", old),
    )
    part = db.execute(
        "SELECT tableoid::regclass::text FROM tracking.track_event WHERE event_name = 'backfill'"
    ).fetchone()[0]
    assert part == "tracking.track_event_default"
    found = pk.alerts(db)
    assert found and found[0]["rows_in_default"] >= 1
    assert found[0]["min_occurred_at"].startswith("2023-05-06")
    assert pk.alerts(db, threshold=10_000) == []


def test_ensure_partitions_is_idempotent(db):
    pk.init(db)
    assert pk.ensure_partitions(db, ahead=2) == []      # init 默认已建当月 + 未来 2 月
    created = pk.ensure_partitions(db, ahead=4)
    assert len(created) == 2                             # 只多出两个月
    assert pk.ensure_partitions(db, ahead=4) == []


def test_ahead_builds_expected_months(db):
    pk.init(db)
    pk.ensure_partitions(db, ahead=4)
    today = dt.date.today().replace(day=1)
    want = set()
    cur = today
    for _ in range(5):                                  # 当月 + 4 个月
        want.add(f"track_event_{cur:%Y_%m}")
        cur = (cur + dt.timedelta(days=32)).replace(day=1)
    assert want <= _partitions(db)


def test_drop_removes_schema(db):
    pk.init(db)
    pk.drop(db)
    assert db.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'tracking'").fetchone() is None
