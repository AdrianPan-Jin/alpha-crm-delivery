"""Legacy id mapping table used by the reconciliation script.

One row per (org, entity, source_id, target_id) so the table can represent both
anomalies the reconciliation reports: a source id mapped twice to different
uuids (duplicate) and several source ids mapped to one uuid (many-to-one).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class LegacyMap(Base):
    __tablename__ = "legacy_map"

    org_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    entity: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_legacy_map_target", "target_id"),)


__all__ = ["LegacyMap"]
