"""Visual evidence contracts. No diagnostic fields or calibrated probabilities."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ViewLabel = Literal['front', 'back', 'left', 'right', 'top', 'bottom', 'nameplate', 'close_up', 'additional']
Ordinal = Literal['low', 'medium', 'high']
ISSUE_TYPES = frozenset('corrosion rust crack broken_component damaged_cable damaged_insulation burn_mark discoloration leakage fluid_residue dust_buildup debris missing_component missing_fastener deformation bent_component surface_wear abrasion damaged_housing blocked_ventilation unknown_visible_abnormality'.split())

# An input/output scope guard, not a grounded post-claim verifier. It deliberately
# rejects an entire response rather than paraphrasing a diagnosis into evidence.
OUT_OF_SCOPE = re.compile(
    r'\b(?:diagnos\w*|root[ -]cause|fail\w*|fault\w*|insulation breakdown|'
    r'internal (?:winding|damage|issue|short(?: circuit)?)|electrical imbalance|lubrication|'
    r'overheat\w*|overload\w*|caused by|due to|safe to|unsafe to|'
    r'shut\s*down|replace\w*|repair\w*|recommend\w*|should|must|'
    r'will (?:break|stop)|disconnect\w*|energiz\w*|deenergiz\w*)\b', re.I)


def require_observation(text: str) -> str:
    if OUT_OF_SCOPE.search(text.replace('_', ' ')):
        raise ValueError('Response contains language outside visible-observation scope')
    return text


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class BoundingRegion(StrictModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode='after')
    def inside_image(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError('Bounding region extends outside image')
        return self


class VisibleFinding(StrictModel):
    issue_type: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=700)
    severity: Ordinal
    visual_confidence: Ordinal
    bounding_region: BoundingRegion | None = None

    @field_validator('issue_type')
    @classmethod
    def normalize_issue(cls, value):
        require_observation(value)
        value = re.sub(r'[ -]+', '_', value.lower())
        if value == 'rust':
            return 'corrosion'
        return value if value in ISSUE_TYPES else 'unknown_visible_abnormality'

    @field_validator('location', 'description')
    @classmethod
    def observation_only(cls, value):
        return require_observation(value)


class VisionResult(StrictModel):
    image_summary: str = Field(min_length=1, max_length=700)
    findings: list[VisibleFinding] = Field(max_length=20)

    @field_validator('image_summary')
    @classmethod
    def observation_only(cls, value):
        return require_observation(value)


class ImageInput(StrictModel):
    view_label: ViewLabel = 'additional'
    user_note: str | None = Field(None, max_length=1000)
