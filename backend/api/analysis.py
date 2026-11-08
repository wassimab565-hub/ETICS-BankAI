from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.models.analysis import RunStatus
from backend.models.document import Document, DocumentStatus
from backend.schemas.analysis import (
    FieldOut,
    FieldReviewIn,
    FindingOut,
    FindingReviewIn,
    ResultsOut,
    ReviewOut,
    RunOut,
    StatusOut,
)
from backend.schemas.document import DocumentOut
from backend.services import analysis_repository as repo
from backend.services import progress
from backend.services.pipeline import run_pipeline
from database.connection import get_db

router = APIRouter(tags=["analysis"])

NOTICE = (
    "Aide à la revue : ces résultats sont générés par un modèle et doivent être vérifiés. "
    "Ils ne constituent pas un avis juridique."
)


def _get_document(db: Session, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.post("/documents/{document_id}/analyze", status_code=202)
def start_analysis(
    document_id: int, background: BackgroundTasks, db: Session = Depends(get_db)
):
    doc = _get_document(db, document_id)
    if doc.status == DocumentStatus.processing.value:
        raise HTTPException(status_code=409, detail="Analysis already in progress.")
    doc.status = DocumentStatus.processing.value
    db.commit()
    background.add_task(run_pipeline, document_id)
    return {"document_id": document_id, "status": DocumentStatus.processing.value}


@router.get("/documents/{document_id}/status", response_model=StatusOut)
def get_status(document_id: int, db: Session = Depends(get_db)):
    doc = _get_document(db, document_id)
    run = repo.latest_run(db, document_id)
    state = progress.get(document_id)
    if state is None and doc.status == DocumentStatus.processing.value:
        state = {"stage": "queued", "done": 0, "total": 0}
    return StatusOut(
        document_id=document_id,
        status=doc.status,
        progress=state,
        run_id=run.id if run else None,
        run_status=run.status if run else None,
        review_priority=run.review_priority if run else None,
        error=run.error if run else None,
    )


@router.get("/documents/{document_id}/results", response_model=ResultsOut)
def get_results(document_id: int, db: Session = Depends(get_db)):
    doc = _get_document(db, document_id)
    run = repo.latest_run(db, document_id)
    if run is None:
        raise HTTPException(status_code=404, detail="No analysis for this document yet.")
    if run.status == RunStatus.running.value:
        raise HTTPException(status_code=409, detail="Analysis in progress.")

    fields = [FieldOut.model_validate(f) for f in repo.list_fields(db, run.id)]
    findings = [FindingOut.model_validate(f) for f in repo.list_findings(db, run.id)]
    for item in [*fields, *findings]:
        item.reviews.sort(key=lambda review: review.id)

    return ResultsOut(
        document=DocumentOut.model_validate(doc),
        run=RunOut.model_validate(run),
        analysis_complete=run.status == RunStatus.completed.value,
        notice=NOTICE,
        fields=fields,
        findings=findings,
    )


def _record_review(db: Session, **kwargs) -> ReviewOut:
    try:
        review = repo.add_review(db, **kwargs)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ReviewOut.model_validate(review)


@router.post("/fields/{field_id}/review", response_model=ReviewOut, status_code=201)
def review_field(field_id: int, body: FieldReviewIn, db: Session = Depends(get_db)):
    return _record_review(
        db,
        reviewer_name=body.reviewer_name,
        decision=body.decision,
        field_id=field_id,
        corrected_value=body.corrected_value,
        notes=body.notes,
    )


@router.post("/findings/{finding_id}/review", response_model=ReviewOut, status_code=201)
def review_finding(finding_id: int, body: FindingReviewIn, db: Session = Depends(get_db)):
    return _record_review(
        db,
        reviewer_name=body.reviewer_name,
        decision=body.decision,
        finding_id=finding_id,
        notes=body.notes,
    )