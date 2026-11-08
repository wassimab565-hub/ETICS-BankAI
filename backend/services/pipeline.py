import logging
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.extraction.service import extract_document
from ai_engine.llm.ollama_client import check_ollama
from ai_engine.prompts.extraction import EXTRACTION_PROMPT_VERSION
from ai_engine.prompts.risk_analysis import RISK_PROMPT_VERSION
from ai_engine.toxicity.service import analyze_document
from backend.core.config import BASE_DIR, settings
from backend.models.analysis import AnalysisRun, RunStatus
from backend.models.document import Document, DocumentStatus
from backend.services import analysis_repository as repo
from backend.services import progress
from backend.services.page_repository import save_pages
from database.connection import SessionLocal
from document_processing.loader import parse_document
from document_processing.preprocessing.text_cleaner import clean_pages
from sqlalchemy import select

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()  # one analysis at a time: the model runs on a single GPU


class PipelineError(Exception):
    """A known failure. Its message is safe to store: it never contains document content."""


def run_pipeline(
    document_id: int, session_factory: Callable[[], Session] = SessionLocal
) -> int | None:
    """Analyze one stored document end to end. Returns the run id, or None if it did not start.

    Meant to run in the background: it opens its own session. Only validated results
    are stored, and the model never writes to the database.
    """
    with _LOCK:
        db = session_factory()
        try:
            return _process(db, document_id)
        finally:
            progress.clear(document_id)
            db.close()


def _needs_review(run: AnalysisRun) -> bool:
    return bool(
        run.extraction_failed_chunks
        or run.risk_failed_chunks
        or run.findings
        or any(field.status != "valid" for field in run.fields)
    )

def _document_type(run: AnalysisRun) -> str | None:
    """Document type found by the extraction, only when it passed the validation rules."""
    for field in run.fields:
        if field.field_name == "document_type" and field.status == "valid":
            return field.raw_value.strip().lower()
    return None

def _process(db: Session, document_id: int) -> int | None:
    doc = db.get(Document, document_id)
    if doc is None:
        logger.warning("document %s not found", document_id)
        return None

    doc.status = DocumentStatus.processing.value
    db.commit()
    run = repo.create_run(
        db, document_id, settings.ollama_model, EXTRACTION_PROMPT_VERSION, RISK_PROMPT_VERSION
    )
    run_id = run.id

    try:
        if not check_ollama().get("model_available"):
            raise PipelineError("model unavailable (Ollama not running or model not installed)")

        progress.update(document_id, "reading", 0, 1)
        pages = clean_pages(parse_document(BASE_DIR / doc.file_path, doc.file_type))
        if not any(page.char_count for page in pages):
            raise PipelineError("no extractable text in the document")
        save_pages(db, document_id, pages)
        chunks = chunk_pages(pages)

        progress.update(document_id, "extraction", 0, 1)
        extraction = extract_document(
            chunks, on_progress=lambda done, total: progress.update(document_id, "extraction", done, total)
        )
        if extraction.chunks_total and not extraction.chunks_analyzed:
            raise PipelineError("no chunk could be analyzed by the model")
        repo.save_extraction(db, run, extraction)

        progress.update(document_id, "risk", 0, 1)
        risk = analyze_document(
            chunks, on_progress=lambda done, total: progress.update(document_id, "risk", done, total)
        )
        repo.save_risk(db, run, risk)

        repo.finish_run(db, run)
        doc.review_priority = run.review_priority
        doc.document_type = _document_type(run)
        doc.status = (
            DocumentStatus.needs_review.value if _needs_review(run) else DocumentStatus.processed.value
        )
        db.commit()
        return run_id
    except Exception as exc:
        db.rollback()
        reason = str(exc) if isinstance(exc, PipelineError) else type(exc).__name__
        logger.error("analysis of document %s failed: %s", document_id, reason)
        _mark_failed(db, document_id, run_id, reason)
        return run_id


def _mark_failed(db: Session, document_id: int, run_id: int, reason: str) -> None:
    run = repo.get_run(db, run_id)
    if run is not None:
        repo.fail_run(db, run, reason)
    doc = db.get(Document, document_id)
    if doc is not None:
        doc.status = DocumentStatus.failed.value
        db.commit()

def recover_interrupted(session_factory: Callable[[], Session] = SessionLocal) -> int:
    """After a restart no analysis is really running: close the ones left open.

    Returns the number of documents put back in the 'failed' state.
    """
    with session_factory() as db:
        runs = db.scalars(select(AnalysisRun).where(AnalysisRun.status == RunStatus.running.value))
        for run in list(runs):
            repo.fail_run(db, run, "interrupted by a server restart")
        documents = list(
            db.scalars(select(Document).where(Document.status == DocumentStatus.processing.value))
        )
        for doc in documents:
            doc.status = DocumentStatus.failed.value
        db.commit()
        return len(documents)