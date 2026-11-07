from typing import Literal

from pydantic import BaseModel, Field

from ai_engine.prompts.extraction import EXTRACTION_FIELDS
from ai_engine.prompts.risk_analysis import RISK_CATEGORIES

FieldName = Literal[tuple(EXTRACTION_FIELDS)]
RiskCategory = Literal[tuple(RISK_CATEGORIES)]


class RawExtractedField(BaseModel):
    field_name: FieldName
    value: str | int | float
    unit: str | None = None
    evidence_lines: list[int] = Field(min_length=1, max_length=8)


class ExtractionOutput(BaseModel):
    fields: list[RawExtractedField]


class RawRiskFinding(BaseModel):
    category: RiskCategory
    severity: Literal["low", "medium", "high"]
    evidence_lines: list[int] = Field(min_length=1, max_length=8)
    explanation: str
    suggested_action: str


class RiskOutput(BaseModel):
    findings: list[RawRiskFinding]