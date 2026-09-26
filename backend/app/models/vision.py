"""Step 3 additive schema. Existing equipment state is never written here."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.equipment import Base  # ensures referenced equipment tables are registered


class SessionImage(Base):
    __tablename__ = 'session_images'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey('equipment_sessions.id', ondelete='CASCADE'), index=True)
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey('equipment_catalog.id'))
    view_label: Mapped[str]
    original_filename: Mapped[str]
    content_sha256: Mapped[str | None] = mapped_column(nullable=True)
    use_for_identification: Mapped[bool | None] = mapped_column(nullable=True)
    stored_path: Mapped[str]
    mime_type: Mapped[str]
    user_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    analysis_status: Mapped[str] = mapped_column(default='pending')
    analysis_started_at: Mapped[datetime | None]
    analysis_token: Mapped[UUID | None]
    analysis_error: Mapped[str | None]
    image_summary: Mapped[str | None] = mapped_column(Text)
    raw_vision_results: Mapped[list] = mapped_column(JSONB, default=list)
    __table_args__ = (
        UniqueConstraint('session_id', 'id'),
        CheckConstraint("view_label IN ('front','back','left','right','top','bottom','nameplate','close_up','additional')"),
        CheckConstraint("analysis_status IN ('pending','analyzing','completed','no_clear_abnormality','failed')"),
    )


class VisualFinding(Base):
    __tablename__ = 'visual_findings'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(index=True)
    image_id: Mapped[UUID] = mapped_column(index=True)
    issue_type: Mapped[str]
    location: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str]
    visual_confidence: Mapped[str]
    bounding_region: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(default='vision_model')
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(['session_id', 'image_id'], ['session_images.session_id', 'session_images.id'], ondelete='CASCADE'),
        CheckConstraint("severity IN ('low','medium','high')"),
        CheckConstraint("visual_confidence IN ('low','medium','high')"),
    )


class AggregatedVisualFinding(Base):
    __tablename__ = 'aggregated_visual_findings'
    id: Mapped[UUID] = mapped_column(primary_key=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey('equipment_sessions.id', ondelete='CASCADE'), index=True)
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey('equipment_catalog.id'))
    issue_type: Mapped[str]
    location: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str]
    visual_confidence: Mapped[str]
    supporting_image_ids: Mapped[list] = mapped_column(JSONB)
    supporting_finding_ids: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (
        CheckConstraint("severity IN ('low','medium','high')"),
        CheckConstraint("visual_confidence IN ('low','medium','high')"),
    )
