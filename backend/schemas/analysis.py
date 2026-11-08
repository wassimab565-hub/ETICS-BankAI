from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.schemas.document import DocumentOut


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision: str
    corrected_value: str | None
    notes: str | None
    reviewer_name: str
    reviewed_at: datetime


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    field_name: str
    label: str | None
    raw_value: str  # as returned by the model: never changed by a review
    value_number: float | None
    unit: str | None
    status: str
    issues: list[str]
    page_start: int
    page_end: int
    evidence: str
    reviews: list[ReviewOut]


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    severity: str | None
    explanation: str
    suggested_action: str
    criteria: dict
    model_criteria: dict | None
    status: str
    issues: list[str]
    page_start: int
    page_end: int
    evidence: str
    reviews: list[ReviewOut]


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    model_name: str
    extraction_prompt_version: str
    risk_prompt_version: str
    review_priority: str | None
    extraction_chunks_total: int
    extraction_chunks_analyzed: int
    extraction_failed_chunks: list[int]
    risk_chunks_total: int
    risk_chunks_analyzed: int
    risk_failed_chunks: list[int]
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class ResultsOut(BaseModel):
    document: DocumentOut
    run: RunOut
    analysis_complete: bool  # False: some passages were not analyzed, results may be partial
    notice: str
    fields: list[FieldOut]
    findings: list[FindingOut]


class StatusOut(BaseModel):
    document_id: int
    status: str
    progress: dict | None = None
    run_id: int | None = None
    run_status: str | None = None
    review_priority: str | None = None
    error: str | None = None


class FieldReviewIn(BaseModel):
    reviewer_name: str
    decision: str  # confirmed | not_confirmed | needs_more_context
    corrected_value: str | None = None
    notes: str | None = None


class FindingReviewIn(BaseModel):
    reviewer_name: str
    decision: str
    notes: str | None = None