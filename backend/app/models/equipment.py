"""Additive Step 2 tables; Step 1 document/vector tables are unchanged."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.document import Base


class Equipment(Base):
    __tablename__ = "equipment_catalog"
    id: Mapped[str] = mapped_column(primary_key=True)
    manufacturer: Mapped[str]
    equipment_family: Mapped[str] = mapped_column(index=True)
    model_name: Mapped[str] = mapped_column(unique=True)
    model_number_pattern: Mapped[str]
    product_type: Mapped[str]
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    voltage_range: Mapped[str | None]
    current_range: Mapped[str | None]
    power_range: Mapped[str | None]
    source_url: Mapped[str]
    related_document_number: Mapped[str | None]
    retrieval_model: Mapped[str]
    retrieval_family: Mapped[str]


class EquipmentSession(Base):
    __tablename__ = "equipment_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    session_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_equipment_text: Mapped[str | None] = mapped_column(Text)
    raw_ocr_text: Mapped[str] = mapped_column(Text, default="")
    parsed_ocr_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    ocr_results: Mapped[list] = mapped_column(JSONB, default=list)
    input_identifiers: Mapped[list] = mapped_column(JSONB, default=list)
    ranked_candidates: Mapped[list] = mapped_column(JSONB, default=list)
    mismatch_warnings: Mapped[list] = mapped_column(JSONB, default=list)
    selected_candidate: Mapped[str | None] = mapped_column(ForeignKey("equipment_catalog.id"))
    confirmed_equipment_id: Mapped[str | None] = mapped_column(ForeignKey("equipment_catalog.id"))
    confirmation_status: Mapped[str] = mapped_column(default="UNCONFIRMED")
    identification_revision: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("owner_user_id IS NULL OR (session_name IS NOT NULL AND session_name = btrim(session_name) AND char_length(session_name) BETWEEN 1 AND 100)", name="owned_session_name"),
        CheckConstraint("confirmation_status IN ('UNCONFIRMED','SUGGESTED','CONFIRMED','REJECTED')"),
        CheckConstraint("(confirmation_status = 'CONFIRMED') = (confirmed_equipment_id IS NOT NULL)"),
        CheckConstraint("confirmed_equipment_id IS NULL OR selected_candidate = confirmed_equipment_id"),
    )
