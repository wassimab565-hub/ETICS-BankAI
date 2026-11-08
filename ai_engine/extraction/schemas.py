from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ValueKind(str, Enum):
    text = "text"
    number = "number"
    money = "money"
    percent = "percent"
    date = "date"
    duration = "duration"
    classification = "classification"


# Kind of value expected for each field (used by the validation rules of phase 5.4).
# Must contain exactly the fields of EXTRACTION_FIELDS (checked by a test).
FIELD_KINDS: dict[str, ValueKind] = {
    "document_title": ValueKind.text,
    "document_type": ValueKind.classification,
    "reference_number": ValueKind.text,
    "bank_name": ValueKind.text,
    "issue_date": ValueKind.date,
    "effective_date": ValueKind.date,
    "expiry_date": ValueKind.date,
    "loan_amount": ValueKind.money,
    "interest_rate": ValueKind.percent,
    "duration_months": ValueKind.duration,
    "installment_amount": ValueKind.money,
    "repayment_frequency": ValueKind.text,
    "application_fee": ValueKind.money,
    "account_fee": ValueKind.money,
    "commission": ValueKind.money,
    "late_payment_penalty": ValueKind.text,
    "early_repayment_fee": ValueKind.text,
    "termination_notice_period": ValueKind.duration,
    "termination_conditions": ValueKind.text,
}


class ValidationStatus(str, Enum):
    valid = "valid"
    needs_review = "needs_review"
    rejected = "rejected"


class FieldSource(BaseModel):
    """Where a value comes from: the verbatim evidence and its location."""

    chunk_index: int
    page_start: int
    page_end: int
    line_start: int
    line_end: int
    evidence: str


class ExtractedField(BaseModel):
    field_name: str
    label: str | None = None  # what the value applies to (service, card, fee line)
    raw_value: str  # value as returned by the model, kept as text
    value_number: float | None = None  # filled by normalization (phase 5.4)
    unit: str | None = None
    source: FieldSource
    status: ValidationStatus = ValidationStatus.needs_review
    issues: list[str] = Field(default_factory=list)

    @field_validator("field_name")
    @classmethod
    def known_field(cls, value: str) -> str:
        if value not in FIELD_KINDS:
            raise ValueError(f"unknown field: {value}")
        return value


class ExtractionResult(BaseModel):
    model_name: str
    prompt_version: str
    chunks_total: int = 0
    chunks_analyzed: int = 0
    failed_chunks: list[int] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """False when some chunks could not be analyzed: a missing field may be a failure."""
        return not self.failed_chunks

    def missing_fields(self) -> list[str]:
        """Fields with no usable value. Check is_complete before reading this as 'absent'."""
        found = {f.field_name for f in self.fields if f.status != ValidationStatus.rejected}
        return [name for name in FIELD_KINDS if name not in found]