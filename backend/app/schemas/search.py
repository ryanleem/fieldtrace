from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=2000)
    equipment_model: str | None = None
    equipment_family: str | None = None
    document_id: UUID | None = None
    top_k: int = Field(default_factory=lambda: get_settings().hybrid_top_k, ge=1, le=100)


class Evidence(BaseModel):
    rank: int
    chunk_id: UUID
    document_id: UUID
    document_title: str
    source_url: str | None
    citation_url: str | None
    document_number: str | None
    revision: str | None
    equipment_model: str | None
    equipment_family: str | None
    page_number: int = Field(description="1-based physical PDF page, not printed manual numbering")
    printed_page_label: str | None
    section_title: str | None
    content_type: str
    chunk_index: int
    chunk_text: str
    source_blocks: list
    safety_context: list
    extraction_notes: list
    semantic_rank: int | None = None
    semantic_score: float | None = None
    keyword_rank: int | None = None
    keyword_score: float | None = None
    rrf_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[Evidence]
