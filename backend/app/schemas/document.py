from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    filename: str = Field(min_length=1)
    title: str = Field(min_length=1)
    manufacturer: str | None = None
    equipment_family: str | None = None
    equipment_model: str | None = None
    document_type: str | None = None
    document_number: str | None = None
    revision: str | None = None
    source_url: str | None = None
    verified_sha256: str | None = None
    metadata_verification: dict = Field(default_factory=dict)


class IngestResult(BaseModel):
    document_id: UUID
    pages_processed: int
    chunks_created: int
    duplicate: bool = False
    warnings: list = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
