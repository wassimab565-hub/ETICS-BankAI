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
    label: str | None = None
    evidence_lines: list[int] = Field(min_length=1, max_length=5)


class ExtractionOutput(BaseModel):
    # maxItems is only a hint for the model's output format, not a validation rule
    fields: list[RawExtractedField] = Field(json_schema_extra={"maxItems": 30})


class RawRiskFinding(BaseModel):
    category: RiskCategory
    severity: Literal["low", "medium", "high"]
    evidence_lines: list[int] = Field(min_length=1, max_length=3)
    explanation: str
    suggested_action: str


class RiskOutput(BaseModel):
    findings: list[RawRiskFinding] = Field(json_schema_extra={"maxItems": 3})