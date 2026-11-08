import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

import backend.models.document  # noqa: F401  (the documents table must exist for the foreign keys)
from database.connection import Base


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    completed_with_errors = "completed_with_errors"  # some chunks could not be analyzed
    failed = "failed"


class ReviewDecisionValue(str, enum.Enum):
    confirmed = "confirmed"
    not_confirmed = "not_confirmed"
    needs_more_context = "needs_more_context"


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    model_name: Mapped[str] = mapped_column(String(100))
    extraction_prompt_version: Mapped[str] = mapped_column(String(50))
    risk_prompt_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default=RunStatus.running.value)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    extraction_chunks_total: Mapped[int] = mapped_column(default=0)
    extraction_chunks_analyzed: Mapped[int] = mapped_column(default=0)
    extraction_failed_chunks: Mapped[list] = mapped_column(JSON, default=list)
    risk_chunks_total: Mapped[int] = mapped_column(default=0)
    risk_chunks_analyzed: Mapped[int] = mapped_column(default=0)
    risk_failed_chunks: Mapped[list] = mapped_column(JSON, default=list)

    review_priority: Mapped[str | None] = mapped_column(String(10))
    error: Mapped[str | None] = mapped_column(Text)

    fields: Mapped[list["ExtractedFieldRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    findings: Mapped[list["RiskFindingRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ExtractedFieldRow(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str | None] = mapped_column(String(255))
    raw_value: Mapped[str] = mapped_column(Text)  # value as returned by the model
    value_number: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    issues: Mapped[list] = mapped_column(JSON, default=list)

    chunk_index: Mapped[int]
    page_start: Mapped[int]
    page_end: Mapped[int]
    line_start: Mapped[int]
    line_end: Mapped[int]
    evidence: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")

    run: Mapped["AnalysisRun"] = relationship(back_populates="fields")
    reviews: Mapped[list["ReviewDecision"]] = relationship(
        cascade="all, delete-orphan"
    )


class RiskFindingRow(Base):
    __tablename__ = "risk_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str | None] = mapped_column(String(10))
    explanation: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)
    criteria: Mapped[dict] = mapped_column(JSON)  # after the code adjustments
    model_criteria: Mapped[dict | None] = mapped_column(JSON)  # model answers, untouched
    status: Mapped[str] = mapped_column(String(20))
    issues: Mapped[list] = mapped_column(JSON, default=list)

    chunk_index: Mapped[int]
    page_start: Mapped[int]
    page_end: Mapped[int]
    line_start: Mapped[int]
    line_end: Mapped[int]
    evidence: Mapped[str] = mapped_column(Text)

    run: Mapped["AnalysisRun"] = relationship(back_populates="findings")
    reviews: Mapped[list["ReviewDecision"]] = relationship(
        cascade="all, delete-orphan"
    )


class ReviewDecision(Base):
    """A human decision on one extracted field OR one risk finding (never both)."""

    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint(
            "(field_id IS NULL) <> (finding_id IS NULL)",
            name="ck_review_exactly_one_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int | None] = mapped_column(
        ForeignKey("extracted_fields.id", ondelete="CASCADE"), index=True
    )
    finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("risk_findings.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(String(30))
    corrected_value: Mapped[str | None] = mapped_column(Text)  # the model value stays untouched
    notes: Mapped[str | None] = mapped_column(Text)
    reviewer_name: Mapped[str] = mapped_column(String(100))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )