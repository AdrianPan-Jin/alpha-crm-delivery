"""Founder-podcast attribution domain: episodes, intro requests, related clicks.

Ticket: S6-POD-041 - connection requests driven by programs and related
recommendation conversion attribution. See docs/metrics-podcast-attribution.md.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from ..models import Timestamped, UUIDPk

INTRO_STATUSES = ("submitted", "staff_approved", "accepted", "rejected")
RELATED_KINDS = ("event", "course", "opportunity")
CONVERSION_KINDS = ("intro_request", "event_signup", "course_signup", "opportunity_request")
SOURCES = ("direct", "assisted")


class PodcastEpisode(UUIDPk, Timestamped, Base):
    __tablename__ = "podcast_episodes"

    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    site_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creator_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    __table_args__ = (
        Index("ix_podcast_episodes_org_published", "org_id", "published_at"),
        CheckConstraint("char_length(title) between 1 and 200", name="ck_episode_title_len"),
    )


class PodcastIntroRequest(UUIDPk, Timestamped, Base):
    __tablename__ = "podcast_intro_requests"

    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    site_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("podcast_episodes.id", ondelete="CASCADE"), nullable=False
    )
    guest_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    requested_by_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="submitted")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status in ('submitted','staff_approved','accepted','rejected')",
            name="ck_intro_request_status",
        ),
        Index("ix_intro_requests_episode_created", "org_id", "episode_id", "created_at"),
    )


class PodcastRelatedClick(UUIDPk, Timestamped, Base):
    __tablename__ = "podcast_related_clicks"

    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    site_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("podcast_episodes.id", ondelete="CASCADE"), nullable=False
    )
    related_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    related_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "related_kind in ('event','course','opportunity')", name="ck_related_click_kind"
        ),
        # the assisted-attribution lookup: latest click by (user, kind, target)
        Index(
            "ix_related_clicks_lookup",
            "org_id",
            "user_id",
            "related_kind",
            "related_id",
            "clicked_at",
        ),
    )


class EpisodeConversionEvent(UUIDPk, Timestamped, Base):
    """Individual attribution rows. Users who disabled personalised recommendations
    are intentionally absent here - their conversions live in the stats totals only."""

    __tablename__ = "episode_conversion_events"

    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    site_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("podcast_episodes.id", ondelete="CASCADE"), nullable=False
    )
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    conversion_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind in ('intro_request','event_signup','course_signup','opportunity_request')",
            name="ck_conversion_kind",
        ),
        CheckConstraint("source in ('direct','assisted')", name="ck_conversion_source"),
        UniqueConstraint(
            "org_id", "episode_id", "kind", "target_id", "user_id", name="uq_conversion_once"
        ),
        Index("ix_conversion_events_stat", "org_id", "stat_date", "episode_id"),
    )


class EpisodeConversionStat(UUIDPk, Timestamped, Base):
    __tablename__ = "episode_conversion_stats"

    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    site_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    episode_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("podcast_episodes.id", ondelete="CASCADE"), nullable=False
    )
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    intro_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intro_staff_approved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intro_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assisted_event_signups: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assisted_course_signups: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assisted_opportunity_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("org_id", "episode_id", "stat_date", name="uq_episode_stat_day"),
        Index("ix_episode_stats_date", "org_id", "stat_date"),
        CheckConstraint(
            "intro_requests >= 0 and intro_staff_approved >= 0 and intro_accepted >= 0",
            name="ck_intro_counts_non_negative",
        ),
    )


__all__ = [
    "PodcastEpisode",
    "PodcastIntroRequest",
    "PodcastRelatedClick",
    "EpisodeConversionEvent",
    "EpisodeConversionStat",
    "INTRO_STATUSES",
    "RELATED_KINDS",
    "CONVERSION_KINDS",
    "SOURCES",
]
