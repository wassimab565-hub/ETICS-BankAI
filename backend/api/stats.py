from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.analysis import AnalysisRun, RiskFindingRow
from backend.models.document import Document
from database.connection import get_db

router = APIRouter(tags=["stats"])

NOTICE = (
    "Compteurs d'aide à la revue : ils n'indiquent pas la conformité ou la "
    "non-conformité d'un document."
)


def _counts(db: Session, column, missing: str, where=None) -> dict:
    query = select(column, func.count()).group_by(column)
    if where is not None:
        query = query.where(where)
    return {(key if key is not None else missing): n for key, n in db.execute(query).all()}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    # findings of the latest analysis of each document only
    latest_runs = select(func.max(AnalysisRun.id)).group_by(AnalysisRun.document_id)
    in_latest = RiskFindingRow.run_id.in_(latest_runs)
    return {
        "notice": NOTICE,
        "documents_total": db.scalar(select(func.count()).select_from(Document)),
        "documents_by_status": _counts(db, Document.status, "unknown"),
        "documents_by_review_priority": _counts(db, Document.review_priority, "not_assessed"),
        "documents_by_type": _counts(db, Document.document_type, "unknown"),
        "documents_with_findings": db.scalar(
            select(func.count(func.distinct(RiskFindingRow.run_id))).where(in_latest)
        ),
        "findings_by_category": _counts(db, RiskFindingRow.category, "unknown", in_latest),
        "findings_by_severity": _counts(db, RiskFindingRow.severity, "unknown", in_latest),
    }