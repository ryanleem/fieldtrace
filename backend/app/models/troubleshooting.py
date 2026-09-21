from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.equipment import Base


class TroubleshootingSession(Base):
    __tablename__ = 'troubleshooting_sessions'
    session_id: Mapped[UUID] = mapped_column(ForeignKey('equipment_sessions.id', ondelete='CASCADE'), primary_key=True)
    equipment_revision: Mapped[int]
    revision: Mapped[int] = mapped_column(default=0)
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    current: Mapped[dict] = mapped_column(JSONB, default=dict)
    run_token: Mapped[UUID | None]
    run_started_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TroubleshootingRun(Base):
    __tablename__ = 'troubleshooting_runs'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey('equipment_sessions.id', ondelete='CASCADE'), index=True)
    input_revision: Mapped[int]
    equipment_revision: Mapped[int]
    context_fingerprint: Mapped[str]
    status: Mapped[str]
    audit: Mapped[dict] = mapped_column(JSONB, default=dict)
    final: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
