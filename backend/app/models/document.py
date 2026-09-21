from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CorpusConfig(Base):
    __tablename__ = "corpus_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str]
    revision: Mapped[str | None]
    dimensions: Mapped[int]
    pipeline_version: Mapped[str]
    __table_args__ = (CheckConstraint("id = 1"),)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str]
    manufacturer: Mapped[str | None]
    equipment_family: Mapped[str | None] = mapped_column(index=True)
    equipment_model: Mapped[str | None] = mapped_column(index=True)
    document_type: Mapped[str | None]
    document_number: Mapped[str | None]
    revision: Mapped[str | None]
    source_url: Mapped[str | None]
    local_path: Mapped[str]
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    pages_processed: Mapped[int]
    chunks_created: Mapped[int]
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    metadata_verification: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DocumentPage(Base):
    __tablename__ = "document_pages"
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    page_number: Mapped[int] = mapped_column(primary_key=True)
    printed_page_label: Mapped[str | None]
    extracted_text: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str]
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    __table_args__ = (CheckConstraint("page_number >= 1"),)
