"""Step 4 contracts; separate from the unchanged visible-observation taxonomy."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(min_length=1, max_length=1200)]
Items = Annotated[list[Text], Field(max_length=30)]
IDs = Annotated[list[str], Field(max_length=8)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Measurement(Contract):
    name: Text
    value: str = Field(min_length=1, max_length=100)
    unit: str = Field(max_length=80)
    location: str = Field(default='', max_length=200)


class TroubleshootingInput(Contract):
    reported_symptoms: Items = Field(default_factory=list)
    technician_notes: Items = Field(default_factory=list)
    measurements: list[Measurement] = Field(default_factory=list, max_length=30)
    checks_completed: Items = Field(default_factory=list)
    ruled_out_causes: Items = Field(default_factory=list)
    confirmed_observations: Items = Field(default_factory=list)
    answer: Text | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class SymptomInput(Contract):
    symptom: Text


class EvidenceRating(Contract):
    chunk_id: str
    relevance: Literal['RELEVANT', 'PARTIALLY_RELEVANT', 'NOT_RELEVANT']
    issue: Text
    reason: Text


class EvidenceReview(Contract):
    chunks: list[EvidenceRating] = Field(max_length=12)
    strength: Literal['STRONG', 'WEAK']
    missing_information: Items


class ConflictReview(Contract):
    relationship: Literal['CONSISTENT', 'COMPLEMENTARY', 'CONFLICTING', 'DIFFERENT_APPLICABILITY']
    chunk_ids: IDs
    explanation: Text


class Cause(Contract):
    label: Text
    rationale: Text
    claim_ids: IDs


class TechnicalClaim(Contract):
    claim_id: str = Field(min_length=1, max_length=80)
    text: Text
    citation_chunk_ids: IDs


class Action(Contract):
    action: Text
    citation_chunk_ids: IDs


class Candidate(Contract):
    primary_cause: Cause | None
    alternative_causes: list[Cause] = Field(max_length=3)
    technical_claims: list[TechnicalClaim] = Field(max_length=8)
    recommended_actions: list[Action] = Field(max_length=5)
    next_question: Text | None
    missing_information: Items


class Verification(Contract):
    status: Literal['SUPPORTED', 'PARTIAL', 'UNSUPPORTED']
    explanation: Text
    revised_text: Text | None


STAGE_SCHEMAS = {'review': EvidenceReview, 'conflict': ConflictReview,
                 'candidate': Candidate, 'verify': Verification}
