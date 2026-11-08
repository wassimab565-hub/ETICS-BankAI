from enum import Enum

from pydantic import BaseModel, Field, field_validator

from ai_engine.extraction.schemas import FieldSource, ValidationStatus
from ai_engine.prompts.risk_analysis import RISK_CATEGORIES


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskCriteria(BaseModel):
    """The three yes/no answers of the model. The severity is computed from them by code."""

    impacts_customer: bool
    unclear_for_customer: bool
    bank_decides_alone: bool


class RiskFinding(BaseModel):
    category: str
    explanation: str
    suggested_action: str
    criteria: RiskCriteria
    severity: Severity | None = None  # computed by code (phase 6.3)
    source: FieldSource
    status: ValidationStatus = ValidationStatus.needs_review
    issues: list[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        if value not in RISK_CATEGORIES:
            raise ValueError(f"unknown category: {value}")
        return value


class RiskResult(BaseModel):
    model_name: str
    prompt_version: str
    chunks_total: int = 0
    chunks_analyzed: int = 0
    failed_chunks: list[int] = Field(default_factory=list)
    findings: list[RiskFinding] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """False when some chunks could not be analyzed: 'no finding' may be a failure."""
        return not self.failed_chunks