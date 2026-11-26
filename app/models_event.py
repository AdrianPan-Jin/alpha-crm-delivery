"""Event registration domain (S3-MINI-046).

Three tables behind the mini-program signup flow:

* ``event_signups``  — one live ``confirmed`` signup per (event, member);
  cancelled rows keep the history, so re-signing after a cancel is allowed.
* ``event_tickets``  — one e-ticket per signup (unique).
* ``event_checkins`` — one check-in per signup (unique).

All three carry the unified seven columns and store money in cents.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import Timestamped, Tenant, UUIDPk

SIGNUP_STATUSES = ("pending", "confirmed", "cancelled", "waitlisted")
CONTACT_KEYS = ("phone", "email", "wechat")


class EventSignup(Base, UUIDPk, Tenant, Timestamped):
    __tablename__ = "event_signups"

    event_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))
    form_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_signups_event_member_alive",
            "event_id",
            "member_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status <> 'cancelled'"),
        ),
        CheckConstraint(
            "status IN ('pending','confirmed','cancelled','waitlisted')", name="ck_signups_status"
        ),
        CheckConstraint("seat_count >= 1", name="ck_signups_seat_count"),
    )


class EventTicket(Base, UUIDPk, Tenant, Timestamped):
    __tablename__ = "event_tickets"

    signup_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("event_signups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    qr_payload: Mapped[str] = mapped_column(String(256), nullable=False, server_default=text("''"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("uq_tickets_signup_alive", "signup_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_tickets_org_no_alive", "org_id", "ticket_no", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )


class EventCheckin(Base, UUIDPk, Tenant, Timestamped):
    __tablename__ = "event_checkins"

    signup_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("event_signups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    method: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'qr'"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("uq_checkins_signup", "signup_id", unique=True),
        CheckConstraint("method IN ('qr','manual')", name="ck_checkins_method"),
    )


def has_contact_keys(payload: dict) -> bool:
    """True when a form snapshot still carries direct contact identifiers."""
    return any(k in payload for k in CONTACT_KEYS)


__all__ = ["EventSignup", "EventTicket", "EventCheckin", "has_contact_keys"]
