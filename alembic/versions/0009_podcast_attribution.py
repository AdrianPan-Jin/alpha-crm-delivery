"""podcast attribution (S6-POD-041)

episodes, intro requests, related clicks, per-conversion rows and the daily
per-episode statistics table consumed by the dashboard.

Revision ID: 0009_podcast_attribution
Revises: 0008_company_lifecycle
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "podcast_episodes",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("published_at", TS, nullable=False),
        sa.Column("creator_user_id", UUID),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TS),
        sa.CheckConstraint("char_length(title) between 1 and 200", name="ck_episode_title_len"),
    )
    op.create_index(
        "ix_podcast_episodes_org_published", "podcast_episodes", ["org_id", "published_at"]
    )

    op.create_table(
        "podcast_intro_requests",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column(
            "episode_id",
            UUID,
            sa.ForeignKey("podcast_episodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("guest_id", UUID),
        sa.Column("requested_by_user_id", UUID, nullable=False),
        sa.Column("status", sa.String(16), server_default="submitted", nullable=False),
        sa.Column("decided_at", TS),
        sa.Column("accepted_at", TS),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TS),
        sa.CheckConstraint(
            "status in ('submitted','staff_approved','accepted','rejected')",
            name="ck_intro_request_status",
        ),
    )
    op.create_index(
        "ix_intro_requests_episode_created",
        "podcast_intro_requests",
        ["org_id", "episode_id", "created_at"],
    )

    op.create_table(
        "podcast_related_clicks",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column(
            "episode_id",
            UUID,
            sa.ForeignKey("podcast_episodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("related_kind", sa.String(16), nullable=False),
        sa.Column("related_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("clicked_at", TS, nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TS),
        sa.CheckConstraint(
            "related_kind in ('event','course','opportunity')", name="ck_related_click_kind"
        ),
    )
    op.create_index(
        "ix_related_clicks_lookup",
        "podcast_related_clicks",
        ["org_id", "user_id", "related_kind", "related_id", "clicked_at"],
    )

    op.create_table(
        "episode_conversion_events",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column(
            "episode_id",
            UUID,
            sa.ForeignKey("podcast_episodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stat_date", sa.Date, nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("conversion_at", TS, nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TS),
        sa.CheckConstraint(
            "kind in ('intro_request','event_signup','course_signup','opportunity_request')",
            name="ck_conversion_kind",
        ),
        sa.CheckConstraint("source in ('direct','assisted')", name="ck_conversion_source"),
        sa.UniqueConstraint(
            "org_id", "episode_id", "kind", "target_id", "user_id", name="uq_conversion_once"
        ),
    )
    op.create_index(
        "ix_conversion_events_stat", "episode_conversion_events", ["org_id", "stat_date", "episode_id"]
    )

    op.create_table(
        "episode_conversion_stats",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID, nullable=False),
        sa.Column("site_id", UUID),
        sa.Column(
            "episode_id",
            UUID,
            sa.ForeignKey("podcast_episodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stat_date", sa.Date, nullable=False),
        sa.Column("intro_requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("intro_staff_approved", sa.Integer, nullable=False, server_default="0"),
        sa.Column("intro_accepted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assisted_event_signups", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assisted_course_signups", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assisted_opportunity_requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", TS),
        sa.UniqueConstraint("org_id", "episode_id", "stat_date", name="uq_episode_stat_day"),
        sa.CheckConstraint(
            "intro_requests >= 0 and intro_staff_approved >= 0 and intro_accepted >= 0",
            name="ck_intro_counts_non_negative",
        ),
    )
    op.create_index("ix_episode_stats_date", "episode_conversion_stats", ["org_id", "stat_date"])


def downgrade() -> None:
    op.drop_table("episode_conversion_stats")
    op.drop_table("episode_conversion_events")
    op.drop_table("podcast_related_clicks")
    op.drop_table("podcast_intro_requests")
    op.drop_table("podcast_episodes")
