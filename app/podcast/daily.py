"""CLI entry point of the daily attribution job.

    python -m app.podcast.daily --date 2026-11-26
    python -m app.podcast.daily --backfill 2026-11-20:2026-11-26

Runs after the listening summary of the day; re-running a date is idempotent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from uuid import UUID

import psycopg

from .attribution import compute_range
from .stubs import ConversionSource, PreferenceSource, StaticConversionSource, StaticPreferenceSource

DEFAULT_ORG = UUID("11111111-1111-1111-1111-111111111111")


def _conn() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/alpha")
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def _days(spec: str) -> list[date]:
    if ":" in spec:
        start, end = spec.split(":", 1)
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        return [a + timedelta(days=i) for i in range((b - a).days + 1)]
    return [date.fromisoformat(spec)]


def main(argv: list[str] | None = None, conversion_source: ConversionSource | None = None,
         preference_source: PreferenceSource | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="single day, YYYY-MM-DD")
    group.add_argument("--backfill", help="inclusive range, START:END")
    ap.add_argument("--org", default=str(DEFAULT_ORG))
    args = ap.parse_args(argv)

    source = conversion_source or StaticConversionSource([])
    prefs = preference_source or StaticPreferenceSource([])
    days = _days(args.date or args.backfill)

    with _conn() as conn:
        results = compute_range(conn, UUID(args.org), days, source, prefs)
        conn.commit()

    print(json.dumps(
        {
            "days": [r.day.isoformat() for r in results],
            "totals": [
                {"day": r.day.isoformat(), **r.totals(), "detail_skipped": r.detail_skipped,
                 "events_written": r.events_written}
                for r in results
            ],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
