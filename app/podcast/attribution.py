"""Attribution engine for the founder podcast series (S6-POD-041).

Rules implemented here (mirrored in docs/metrics-podcast-attribution.md):

1. Direct attribution - per episode and stat_date:
   intro_requests      = requests created on that date
   intro_staff_approved= requests whose staff decision landed on that date
   intro_accepted      = requests accepted on that date
2. Assisted attribution - a click at T assists a conversion at C for the same
   item when 0 <= C - T <= 24 hours. The window is closed at 24h, so 25h never
   counts and 23h does.
3. The same user + same item + several episodes: the conversion belongs to the
   episode of the MOST RECENT click only (tie-break: later clicked_at, then
   lower episode id, so the result is deterministic).
4. Users who disabled personalised recommendations are still counted in the
   stats totals, but no per-user row is written to episode_conversion_events.
5. Re-running a date is idempotent: rows for that (org, stat_date) are replaced
   inside the caller's transaction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from uuid import UUID

from .stubs import CONVERSION_KIND_TO_RELATED, Conversion, ConversionSource, PreferenceSource

WINDOW = timedelta(hours=24)

ASSISTED_COLUMN = {
    "event_signup": "assisted_event_signups",
    "course_signup": "assisted_course_signups",
    "opportunity_request": "assisted_opportunity_requests",
}


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


@dataclass
class DayResult:
    day: date
    stats: dict[UUID, dict[str, int]] = field(default_factory=dict)
    events_written: int = 0
    detail_skipped: int = 0

    def totals(self) -> dict[str, int]:
        out = {
            "episodes": len(self.stats),
            "intro_requests": 0,
            "intro_staff_approved": 0,
            "intro_accepted": 0,
            "assisted_event_signups": 0,
            "assisted_course_signups": 0,
            "assisted_opportunity_requests": 0,
        }
        for row in self.stats.values():
            for key, value in row.items():
                out[key] += value
        return out


def _empty_stats() -> dict[str, int]:
    return {
        "intro_requests": 0,
        "intro_staff_approved": 0,
        "intro_accepted": 0,
        "assisted_event_signups": 0,
        "assisted_course_signups": 0,
        "assisted_opportunity_requests": 0,
    }


def _latest_click(conn, org_id: UUID, conv: Conversion) -> UUID | None:
    """Episode of the most recent click for this (user, item) before the conversion."""
    rows = conn.execute(
        """
        SELECT episode_id, clicked_at
          FROM podcast_related_clicks
         WHERE org_id = %s AND user_id = %s AND related_kind = %s AND related_id = %s
           AND deleted_at IS NULL
           AND clicked_at <= %s AND clicked_at >= %s
         ORDER BY clicked_at DESC, episode_id ASC
         LIMIT 1
        """,
        (
            org_id,
            conv.user_id,
            CONVERSION_KIND_TO_RELATED[conv.kind],
            conv.target_id,
            conv.occurred_at,
            conv.occurred_at - WINDOW,
        ),
    ).fetchall()
    return rows[0][0] if rows else None


def _direct_counts(conn, org_id: UUID, day: date) -> dict[UUID, dict[str, int]]:
    start, end = _day_bounds(day)
    out: dict[UUID, dict[str, int]] = {}

    def bucket(episode_id: UUID) -> dict[str, int]:
        return out.setdefault(episode_id, _empty_stats())

    for episode_id, n in conn.execute(
        """
        SELECT episode_id, count(*) FROM podcast_intro_requests
         WHERE org_id = %s AND deleted_at IS NULL AND created_at >= %s AND created_at < %s
         GROUP BY episode_id
        """,
        (org_id, start, end),
    ).fetchall():
        bucket(episode_id)["intro_requests"] = n

    for episode_id, n in conn.execute(
        """
        SELECT episode_id, count(*) FROM podcast_intro_requests
         WHERE org_id = %s AND deleted_at IS NULL
           AND status IN ('staff_approved','accepted')
           AND decided_at >= %s AND decided_at < %s
         GROUP BY episode_id
        """,
        (org_id, start, end),
    ).fetchall():
        bucket(episode_id)["intro_staff_approved"] = n

    for episode_id, n in conn.execute(
        """
        SELECT episode_id, count(*) FROM podcast_intro_requests
         WHERE org_id = %s AND deleted_at IS NULL AND status = 'accepted'
           AND accepted_at >= %s AND accepted_at < %s
         GROUP BY episode_id
        """,
        (org_id, start, end),
    ).fetchall():
        bucket(episode_id)["intro_accepted"] = n

    return out


def compute_day(
    conn,
    org_id: UUID,
    day: date,
    conversion_source: ConversionSource,
    preference_source: PreferenceSource,
) -> DayResult:
    """Compute (and persist) the per-episode stats of one day. Caller commits."""
    start, end = _day_bounds(day)
    result = DayResult(day=day)

    conn.execute(
        "DELETE FROM episode_conversion_stats WHERE org_id = %s AND stat_date = %s",
        (org_id, day),
    )
    conn.execute(
        "DELETE FROM episode_conversion_events WHERE org_id = %s AND stat_date = %s",
        (org_id, day),
    )

    result.stats = _direct_counts(conn, org_id, day)

    for conv in conversion_source.conversions(start, end):
        episode_id = _latest_click(conn, org_id, conv)
        if episode_id is None:
            continue
        row = result.stats.setdefault(episode_id, _empty_stats())
        column = ASSISTED_COLUMN[conv.kind]
        row[column] += 1

        if not preference_source.personalization_enabled(conv.user_id):
            # totals still include this conversion, but nothing personal is stored
            result.detail_skipped += 1
            continue

        conn.execute(
            """
            INSERT INTO episode_conversion_events
                   (org_id, episode_id, stat_date, kind, target_id, user_id, source, conversion_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'assisted', %s)
            ON CONFLICT (org_id, episode_id, kind, target_id, user_id) DO NOTHING
            """,
            (
                org_id,
                episode_id,
                day,
                conv.kind,
                conv.target_id,
                conv.user_id,
                conv.occurred_at,
            ),
        )
        result.events_written += 1

    for episode_id, row in result.stats.items():
        conn.execute(
            """
            INSERT INTO episode_conversion_stats
                   (org_id, episode_id, stat_date, intro_requests, intro_staff_approved,
                    intro_accepted, assisted_event_signups, assisted_course_signups,
                    assisted_opportunity_requests)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                org_id,
                episode_id,
                day,
                row["intro_requests"],
                row["intro_staff_approved"],
                row["intro_accepted"],
                row["assisted_event_signups"],
                row["assisted_course_signups"],
                row["assisted_opportunity_requests"],
            ),
        )

    return result


def compute_range(
    conn,
    org_id: UUID,
    days: Iterable[date],
    conversion_source: ConversionSource,
    preference_source: PreferenceSource,
) -> list[DayResult]:
    return [compute_day(conn, org_id, d, conversion_source, preference_source) for d in days]


__all__ = ["compute_day", "compute_range", "DayResult", "WINDOW"]
