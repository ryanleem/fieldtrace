from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Computed, ForeignKeyConstraint, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.document import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(index=True)
    page_number: Mapped[int] = mapped_column(index=True)
    section_title: Mapped[str | None]
    content_type: Mapped[str]
    chunk_index: Mapped[int]
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    # Separate raw technical lexemes from stemmed prose. No identifier stemming.
    search_text: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str] = mapped_column(TSVECTOR, Computed(
        "setweight(to_tsvector('simple', search_text), 'A') || "
        "setweight(to_tsvector('english', search_text), 'B')", persisted=True))
    source_blocks: Mapped[list] = mapped_column(JSONB)
    safety_context: Mapped[list] = mapped_column(JSONB, default=list)
    extraction_notes: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["document_id", "page_number"],
                             ["document_pages.document_id", "document_pages.page_number"], ondelete="CASCADE"),
        UniqueConstraint("document_id", "chunk_index"),
        CheckConstraint("page_number >= 1 AND chunk_index >= 0"),
        CheckConstraint("length(trim(chunk_text)) > 0"),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )
