"""S6-POD-041: podcast intro requests and related-recommendation attribution.

Maps to the order's acceptance items:

1. a sign-up 25 h after the click is not counted, 23 h is
2. the same user clicking two episodes then signing up is attributed only to
   the most recent click
3. the three intro-request counts match the fixture data of
   ``podcast_intro_requests``
4. users who disabled personalised recommendations count in totals only
5. the daily job is idempotent and backfill equals a full recompute
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest

from app.podcast.attribution import compute_day, compute_range
from app.podcast.stubs import Conversion, StaticConversionSource, StaticPreferenceSource

ROOT = Path(__file__).resolve().parents[1]
PG_HOST = os.environ.get("PG_HOST", "127.0.0.1")
PG_PORT = int(os.environ.get("PG_PORT", "55432"))
ORG = "11111111-1111-1111-1111-111111111111"
SITE = "22222222-2222-2222-2222-222222222222"
D1 = dt.date(2026, 11, 20)
UTC = dt.timezone.utc


def _admin():
    return psycopg.connect(host=PG_HOST, port=PG_PORT, user="postgres", dbname="postgres", autocommit=True)


def _url(name: str) -> str:
    return f"postgresql+psycopg://postgres@{PG_HOST}:{PG_PORT}/{name}"


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "DATABASE_URL": url},
    )


@pytest.fixture(scope="module")
def db() -> psycopg.Connection:
    name = f"alpha_pod_{uuid.uuid4().hex[:8]}"
    with _admin() as adm:
        adm.execute(f'CREATE DATABASE "{name}"')
    url = _url(name)
    up = _alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stdout + up.stderr
    conn = psycopg.connect(host=PG_HOST, port=PG_PORT, user="postgres", dbname=name)
    yield conn
    conn.close()
    with _admin() as adm:
        adm.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(autouse=True)
def clean(db):
    for t in (
        "episode_conversion_stats",
        "episode_conversion_events",
        "podcast_related_clicks",
        "podcast_intro_requests",
        "podcast_episodes",
    ):
        db.execute(f"DELETE FROM {t}")
    db.commit()
    yield


def _episode(conn, title="ep-1") -> uuid.UUID:
    return conn.execute(
        "INSERT INTO podcast_episodes (org_id, site_id, title, published_at) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (ORG, SITE, title, dt.datetime(2026, 11, 1, tzinfo=UTC)),
    ).fetchone()[0]


def _request(conn, episode, status="submitted", created=None, decided=None, accepted=None, user=None):
    return conn.execute(
        "INSERT INTO podcast_intro_requests "
        "(org_id, site_id, episode_id, requested_by_user_id, status, created_at, decided_at, accepted_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            ORG,
            SITE,
            episode,
            user or uuid.uuid4(),
            status,
            created or dt.datetime.combine(D1, dt.time(10), tzinfo=UTC),
            decided,
            accepted,
        ),
    ).fetchone()[0]


def _click(conn, episode, kind, target, user, at):
    conn.execute(
        "INSERT INTO podcast_related_clicks "
        "(org_id, site_id, episode_id, related_kind, related_id, user_id, clicked_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (ORG, SITE, episode, kind, target, user, at),
    )


def _stats(conn, day=D1):
    rows = conn.execute(
        "SELECT episode_id, intro_requests, intro_staff_approved, intro_accepted, "
        "assisted_event_signups, assisted_course_signups, assisted_opportunity_requests "
        "FROM episode_conversion_stats WHERE org_id = %s AND stat_date = %s",
        (ORG, day),
    ).fetchall()
    return {r[0]: {"intro_requests": r[1], "intro_staff_approved": r[2], "intro_accepted": r[3],
                  "assisted_event_signups": r[4], "assisted_course_signups": r[5],
                  "assisted_opportunity_requests": r[6]} for r in rows}


def test_direct_counts_match_intro_requests(db):
    ep = _episode(db)
    t = dt.datetime.combine(D1, dt.time(9), tzinfo=UTC)
    _request(db, ep, created=t)
    _request(db, ep, created=t + timedelta(hours=1))
    _request(db, ep, created=t + timedelta(hours=2))
    _request(db, ep, status="staff_approved", created=t, decided=t + timedelta(hours=4))
    _request(db, ep, status="accepted", created=t + timedelta(hours=3),
             decided=t + timedelta(hours=5), accepted=t + timedelta(hours=6))
    db.commit()

    compute_day(db, ORG, D1, StaticConversionSource([]), StaticPreferenceSource([]))
    db.commit()

    row = _stats(db)[ep]
    assert row["intro_requests"] == 5
    assert row["intro_staff_approved"] == 2
    assert row["intro_accepted"] == 1


@pytest.mark.parametrize("hours,counted", [(23, 1), (24, 1), (25, 0)])
def test_assisted_window_boundary(db, hours, counted):
    ep = _episode(db)
    user, target = uuid.uuid4(), uuid.uuid4()
    click_at = dt.datetime.combine(D1, dt.time(0, 10), tzinfo=UTC)
    _click(db, ep, "event", target, user, click_at)
    db.commit()

    conv_at = click_at + timedelta(hours=hours)
    src = StaticConversionSource([Conversion("event_signup", target, user, conv_at)])
    stat_day = conv_at.date()
    compute_day(db, ORG, stat_day, src, StaticPreferenceSource([]))
    db.commit()

    assert _stats(db, stat_day).get(ep, {}).get("assisted_event_signups", 0) == counted


def test_most_recent_click_wins(db):
    ep_a, ep_b = _episode(db, "ep-a"), _episode(db, "ep-b")
    user, target = uuid.uuid4(), uuid.uuid4()
    base = dt.datetime.combine(D1, dt.time(8), tzinfo=UTC)
    _click(db, ep_a, "course", target, user, base)
    _click(db, ep_b, "course", target, user, base + timedelta(hours=2))
    db.commit()

    src = StaticConversionSource(
        [Conversion("course_signup", target, user, base + timedelta(hours=3))]
    )
    compute_day(db, ORG, D1, src, StaticPreferenceSource([]))
    db.commit()

    stats = _stats(db)
    assert stats[ep_b]["assisted_course_signups"] == 1
    assert stats.get(ep_a, {}).get("assisted_course_signups", 0) == 0


def test_personalization_disabled_totals_only(db):
    ep = _episode(db)
    user, target = uuid.uuid4(), uuid.uuid4()
    click_at = dt.datetime.combine(D1, dt.time(9), tzinfo=UTC)
    _click(db, ep, "opportunity", target, user, click_at)
    db.commit()

    src = StaticConversionSource(
        [Conversion("opportunity_request", target, user, click_at + timedelta(hours=1))]
    )
    result = compute_day(db, ORG, D1, src, StaticPreferenceSource([user]))
    db.commit()

    assert _stats(db)[ep]["assisted_opportunity_requests"] == 1
    assert result.events_written == 0
    assert result.detail_skipped == 1
    detail = db.execute(
        "SELECT count(*) FROM episode_conversion_events WHERE org_id = %s", (ORG,)
    ).fetchone()[0]
    assert detail == 0


def test_daily_job_idempotent_and_backfill(db):
    ep = _episode(db)
    user, target = uuid.uuid4(), uuid.uuid4()
    t0 = dt.datetime.combine(D1, dt.time(9), tzinfo=UTC)
    _click(db, ep, "event", target, user, t0)
    _request(db, ep, created=t0)
    db.commit()

    src = StaticConversionSource([Conversion("event_signup", target, user, t0 + timedelta(hours=2))])
    prefs = StaticPreferenceSource([])

    compute_day(db, ORG, D1, src, prefs)
    db.commit()
    first = _stats(db)

    compute_day(db, ORG, D1, src, prefs)
    db.commit()
    assert _stats(db) == first

    days = [D1 + timedelta(days=i) for i in range(3)]
    compute_range(db, ORG, days, src, prefs)
    db.commit()
    after_backfill = _stats(db)
    assert after_backfill == first  # the extra days add nothing but must not double count


def test_stats_unique_per_episode_date(db):
    import psycopg.errors as errs

    ep = _episode(db)
    _request(db, ep)  # gives the episode a stats row to collide with
    compute_day(db, ORG, D1, StaticConversionSource([]), StaticPreferenceSource([]))
    db.commit()
    with pytest.raises(errs.UniqueViolation):
        db.execute(
            "INSERT INTO episode_conversion_stats (org_id, episode_id, stat_date) VALUES (%s, %s, %s)",
            (ORG, ep, D1),
        )
    db.rollback()


def test_soft_deleted_click_ignored(db):
    ep = _episode(db)
    user, target = uuid.uuid4(), uuid.uuid4()
    click_at = dt.datetime.combine(D1, dt.time(9), tzinfo=UTC)
    _click(db, ep, "event", target, user, click_at)
    db.execute("UPDATE podcast_related_clicks SET deleted_at = now()")
    db.commit()

    src = StaticConversionSource([Conversion("event_signup", target, user, click_at + timedelta(hours=1))])
    compute_day(db, ORG, D1, src, StaticPreferenceSource([]))
    db.commit()
    assert _stats(db).get(ep, {}).get("assisted_event_signups", 0) == 0
