from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConfirmEquipment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    equipment_id: str = Field(min_length=1, max_length=100)
    identification_revision: int | None = Field(default=None, ge=1)


class EquipmentState(BaseModel):
    session_id: UUID
    entered_equipment_text: str | None
    raw_ocr_text: str
    parsed_ocr_fields: dict
    ocr_results: list
    input_identifiers: list
    ranked_candidates: list
    selected_candidate: str | None
    confirmed_equipment_id: str | None
    confirmation_status: Literal['UNCONFIRMED', 'SUGGESTED', 'CONFIRMED', 'REJECTED']
    identification_revision: int
    confidence: Literal['HIGH', 'MEDIUM', 'LOW'] | None
    mismatch_warnings: list
    confirmation_prompt: str | None
    confirmed_equipment_family: str | None
    confirmed_model: str | None
    retrieval_filters: dict | None
    visual_support: str = 'Appearance is not used for authoritative identification; only visible OCR text is considered.'
    catalog_label: str = 'Prototype equipment catalog for demo/testing.'
