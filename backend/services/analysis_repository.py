from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_engine.extraction.schemas import ExtractedField, ExtractionResult
from ai_engine.toxicity.rules import review_priority
from ai_engine.toxicity.schemas import RiskFinding, RiskResult
from backend.models.analysis import (
    AnalysisRun,
    ExtractedFieldRow,
    ReviewDecision,
    ReviewDecisionValue,
    RiskFindingRow,
    RunStatus,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _field_row(field: ExtractedField) -> ExtractedFieldRow:
    source = field.source
    return ExtractedFieldRow(
        field_name=field.field_name,
        label=field.label,
        raw_value=field.raw_value,
        value_number=field.value_number,
        unit=field.unit,
        status=field.status.value,
        issues=list(field.issues),
        chunk_index=source.chunk_index,
        page_start=source.page_start,
        page_end=source.page_end,
        line_start=source.line_start,
        line_end=source.line_end,
        evidence=source.evidence,
        context=source.context,
    )


def _finding_row(finding: RiskFinding) -> RiskFindingRow:
    source = finding.source
    return RiskFindingRow(
        category=finding.category,
        severity=finding.severity.value if finding.severity else None,
        explanation=finding.explanation,
        suggested_action=finding.suggested_action,
        criteria=finding.criteria.model_dump(),
        model_criteria=finding.model_criteria.model_dump() if finding.model_criteria else None,
        status=finding.status.value,
        issues=list(finding.issues),
        chunk_index=source.chunk_index,
        page_start=source.page_start,
        page_end=source.page_end,
        line_start=source.line_start,
        line_end=source.line_end,
        evidence=source.evidence,
    )


def create_run(
    db: Session,
    document_id: int,
    model_name: str,
    extraction_prompt_version: str,
    risk_prompt_version: str,
) -> AnalysisRun:
    run = AnalysisRun(
        document_id=document_id,
        model_name=model_name,
        extraction_prompt_version=extraction_prompt_version,
        risk_prompt_version=risk_prompt_version,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def save_extraction(db: Session, run: AnalysisRun, result: ExtractionResult) -> None:
    """Store the validated extraction result. Call once per run."""
    run.extraction_chunks_total = result.chunks_total
    run.extraction_chunks_analyzed = result.chunks_analyzed
    run.extraction_failed_chunks = list(result.failed_chunks)
    for field in result.fields:
        run.fields.append(_field_row(field))
    db.commit()


def save_risk(db: Session, run: AnalysisRun, result: RiskResult) -> None:
    """Store the risk findings (already post-processed) and the review priority."""
    run.risk_chunks_total = result.chunks_total
    run.risk_chunks_analyzed = result.chunks_analyzed
    run.risk_failed_chunks = list(result.failed_chunks)
    priority = review_priority(result)
    run.review_priority = priority.value if priority else None
    for finding in result.findings:  # already sorted by severity: ids keep that order
        run.findings.append(_finding_row(finding))
    db.commit()


def finish_run(db: Session, run: AnalysisRun) -> None:
    complete = not run.extraction_failed_chunks and not run.risk_failed_chunks
    status = RunStatus.completed if complete else RunStatus.completed_with_errors
    run.status = status.value
    run.finished_at = _now()
    db.commit()


def fail_run(db: Session, run: AnalysisRun, error: str) -> None:
    """Mark a run as failed. The message must never contain document content."""
    run.status = RunStatus.failed.value
    run.error = error[:500]
    run.finished_at = _now()
    db.commit()


def get_run(db: Session, run_id: int) -> AnalysisRun | None:
    return db.get(AnalysisRun, run_id)


def latest_run(db: Session, document_id: int) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.document_id == document_id)
        .order_by(AnalysisRun.id.desc())
        .limit(1)
    )


def list_fields(db: Session, run_id: int) -> list[ExtractedFieldRow]:
    return list(
        db.scalars(
            select(ExtractedFieldRow)
            .where(ExtractedFieldRow.run_id == run_id)
            .order_by(ExtractedFieldRow.id)
        )
    )


def list_findings(db: Session, run_id: int) -> list[RiskFindingRow]:
    return list(
        db.scalars(
            select(RiskFindingRow)
            .where(RiskFindingRow.run_id == run_id)
            .order_by(RiskFindingRow.id)
        )
    )


def add_review(
    db: Session,
    *,
    reviewer_name: str,
    decision: str,
    field_id: int | None = None,
    finding_id: int | None = None,
    corrected_value: str | None = None,
    notes: str | None = None,
) -> ReviewDecision:
    """Record a human decision on one extracted field or one risk finding.

    The model value is never changed: a correction is stored next to it.
    """
    name = reviewer_name.strip()
    if not name:
        raise ValueError("reviewer name is required")
    try:
        decision_value = ReviewDecisionValue(decision).value
    except ValueError:
        raise ValueError(f"unknown decision: {decision}") from None
    if (field_id is None) == (finding_id is None):
        raise ValueError("a review targets exactly one field or one finding")
    if finding_id is not None and corrected_value is not None:
        raise ValueError("only extracted fields can be corrected")
    if field_id is not None and db.get(ExtractedFieldRow, field_id) is None:
        raise LookupError(f"unknown field: {field_id}")
    if finding_id is not None and db.get(RiskFindingRow, finding_id) is None:
        raise LookupError(f"unknown finding: {finding_id}")

    review = ReviewDecision(
        field_id=field_id,
        finding_id=finding_id,
        decision=decision_value,
        corrected_value=corrected_value,
        notes=notes,
        reviewer_name=name,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review