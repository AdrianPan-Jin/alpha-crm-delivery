"""Query stubs for modules this ticket depends on.

Other tickets own event sign-ups, course enrolments, public-opportunity
connection requests and the personalisation preference. Nothing here talks to
the network: the production wiring is documented in the README and each stub
class exposes the exact method the daily job calls, so swapping in an HTTP
client later is a one-line change.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol
from uuid import UUID

CONVERSION_KIND_TO_RELATED = {
    "event_signup": "event",
    "course_signup": "course",
    "opportunity_request": "opportunity",
}


@dataclass(frozen=True)
class Conversion:
    """One conversion produced by another module."""

    kind: str  # 'event_signup' | 'course_signup' | 'opportunity_request'
    target_id: UUID
    user_id: UUID
    occurred_at: datetime


class ConversionSource(Protocol):
    """Interface stub: sign-up / enrolment / request of another module."""

    def conversions(self, start: datetime, end: datetime) -> Iterable[Conversion]:
        """Conversions strictly inside [start, end)."""


class PreferenceSource(Protocol):
    """Interface stub: personalisation preference of a user."""

    def personalization_enabled(self, user_id: UUID) -> bool:
        """False -> the user is excluded from per-user detail rows."""


class StaticConversionSource:
    """Fixture-backed stub used by tests and local runs."""

    def __init__(self, rows: Iterable[Conversion] = ()) -> None:
        self._rows = list(rows)

    def conversions(self, start: datetime, end: datetime) -> Iterable[Conversion]:
        return [r for r in self._rows if start <= r.occurred_at < end]


class StaticPreferenceSource:
    """Fixture-backed stub; users absent from the map are treated as opted in."""

    def __init__(self, disabled: Iterable[UUID] = ()) -> None:
        self._disabled = set(disabled)

    def personalization_enabled(self, user_id: UUID) -> bool:
        return user_id not in self._disabled


__all__ = [
    "Conversion",
    "ConversionSource",
    "PreferenceSource",
    "StaticConversionSource",
    "StaticPreferenceSource",
    "CONVERSION_KIND_TO_RELATED",
]
