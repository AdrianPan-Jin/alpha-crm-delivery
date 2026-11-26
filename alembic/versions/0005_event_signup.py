"""event signup / e-ticket / check-in tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _common_cols() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "event_signups",
        *_common_cols(),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("form_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("seat_count", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("status IN ('pending','confirmed','cancelled','waitlisted')", name="ck_signups_status"),
        sa.CheckConstraint("seat_count >= 1", name="ck_signups_seat_count"),
    )
    op.create_index("ix_event_signups_org_id", "event_signups", ["org_id"])
    op.create_index("ix_event_signups_site_id", "event_signups", ["site_id"])
    op.create_index("ix_event_signups_event_id", "event_signups", ["event_id"])
    op.create_index("ix_event_signups_member_id", "event_signups", ["member_id"])
    op.create_index(
        "uq_signups_event_member_alive",
        "event_signups",
        ["event_id", "member_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status <> 'cancelled'"),
    )

    op.create_table(
        "event_tickets",
        *_common_cols(),
        sa.Column("signup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_no", sa.String(32), nullable=False),
        sa.Column("qr_payload", sa.String(256), nullable=False, server_default=sa.text("''")),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["signup_id"], ["event_signups.id"], name="fk_tickets_signup", ondelete="CASCADE"),
    )
    op.create_index("ix_event_tickets_org_id", "event_tickets", ["org_id"])
    op.create_index("ix_event_tickets_site_id", "event_tickets", ["site_id"])
    op.create_index("ix_event_tickets_signup_id", "event_tickets", ["signup_id"])
    op.create_index("ix_event_tickets_ticket_no", "event_tickets", ["ticket_no"])
    op.create_index(
        "uq_tickets_signup_alive", "event_tickets", ["signup_id"], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_tickets_org_no_alive", "event_tickets", ["org_id", "ticket_no"], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "event_checkins",
        *_common_cols(),
        sa.Column("signup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("method", sa.String(16), nullable=False, server_default=sa.text("'qr'")),
        sa.ForeignKeyConstraint(["signup_id"], ["event_signups.id"], name="fk_checkins_signup", ondelete="CASCADE"),
        sa.CheckConstraint("method IN ('qr','manual')", name="ck_checkins_method"),
    )
    op.create_index("ix_event_checkins_org_id", "event_checkins", ["org_id"])
    op.create_index("ix_event_checkins_site_id", "event_checkins", ["site_id"])
    op.create_index("ix_event_checkins_signup_id", "event_checkins", ["signup_id"])
    op.create_index("uq_checkins_signup", "event_checkins", ["signup_id"], unique=True)


def downgrade() -> None:
    op.drop_table("event_checkins")
    op.drop_table("event_tickets")
    op.drop_table("event_signups")
