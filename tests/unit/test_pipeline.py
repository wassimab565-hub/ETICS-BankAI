import pymupdf
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models.analysis  # noqa: F401
import backend.models.document_page  # noqa: F401
from ai_engine.extraction.schemas import (
    ExtractedField,
    ExtractionResult,
    FieldSource,
    ValidationStatus,
)
from ai_engine.toxicity.schemas import RiskCriteria, RiskFinding, RiskResult, Severity
from backend.models.analysis import AnalysisRun
from backend.models.document import Document
from backend.services import pipeline, progress
from backend.services.page_repository import get_pages
from database.connection import Base
from document_processing.parsers.base import PageText

TEXT = (
    "Frais de tenue de compte: 5 euros par mois\n"
    "Commission d'intervention: 8 euros par operation"
)


@pytest.fixture()
def factory():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def doc_id(factory, tmp_path):
    path = tmp_path / "a.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 100), TEXT, fontsize=14)
    pdf.save(path)
    with factory() as db:
        doc = Document(
            filename="a.pdf",
            file_path=str(path),
            sha256="x" * 64,
            file_type="pdf",
            size_bytes=path.stat().st_size,
        )
        db.add(doc)
        db.commit()
        return doc.id


@pytest.fixture(autouse=True)
def ollama_up(monkeypatch):
    monkeypatch.setattr(
        pipeline, "check_ollama", lambda: {"ollama": "up", "model_available": True}
    )


def source():
    return FieldSource(
        chunk_index=0,
        page_start=1,
        page_end=1,
        line_start=1,
        line_end=2,
        evidence="Frais de tenue de compte: 5 euros par mois",
    )


def extraction_ok(**kwargs):
    field = ExtractedField(
        field_name="account_fee",
        raw_value="5",
        value_number=5.0,
        unit="EUR/month",
        source=source(),
        status=ValidationStatus.valid,
    )
    values = {"chunks_total": 1, "chunks_analyzed": 1, "fields": [field]}
    values.update(kwargs)
    return ExtractionResult(model_name="m", prompt_version="p", **values)


def risk_result(with_finding):
    findings = []
    if with_finding:
        findings = [
            RiskFinding(
                category="termination_changes",
                explanation="x",
                suggested_action="x",
                criteria=RiskCriteria(
                    impacts_customer=True, unclear_for_customer=False, bank_decides_alone=True
                ),
                severity=Severity.medium,
                source=source(),
            )
        ]
    return RiskResult(
        model_name="m",
        prompt_version="p",
        chunks_total=1,
        chunks_analyzed=1,
        findings=findings,
    )


def patch_models(monkeypatch, extraction, risk):
    monkeypatch.setattr(pipeline, "extract_document", lambda chunks, **kw: extraction)
    monkeypatch.setattr(pipeline, "analyze_document", lambda chunks, **kw: risk)


def test_successful_run_needs_review(factory, doc_id, monkeypatch):
    patch_models(monkeypatch, extraction_ok(), risk_result(True))

    run_id = pipeline.run_pipeline(doc_id, factory)

    with factory() as db:
        doc = db.get(Document, doc_id)
        run = db.get(AnalysisRun, run_id)
        assert doc.status == "needs_review"
        assert run.status == "completed"
        assert run.review_priority == "medium"
        assert len(run.fields) == 1 and len(run.findings) == 1
        assert len(get_pages(db, doc_id)) == 1
    assert progress.get(doc_id) is None


def test_clean_document_is_processed(factory, doc_id, monkeypatch):
    patch_models(monkeypatch, extraction_ok(), risk_result(False))

    run_id = pipeline.run_pipeline(doc_id, factory)

    with factory() as db:
        assert db.get(Document, doc_id).status == "processed"
        assert db.get(AnalysisRun, run_id).review_priority == "low"


def test_model_unavailable_fails_the_run(factory, doc_id, monkeypatch):
    monkeypatch.setattr(pipeline, "check_ollama", lambda: {"ollama": "unreachable"})

    run_id = pipeline.run_pipeline(doc_id, factory)

    with factory() as db:
        run = db.get(AnalysisRun, run_id)
        assert db.get(Document, doc_id).status == "failed"
        assert run.status == "failed"
        assert "model unavailable" in run.error
        assert run.finished_at is not None


def test_no_chunk_analyzed_fails_before_the_risk_step(factory, doc_id, monkeypatch):
    all_failed = extraction_ok(chunks_total=2, chunks_analyzed=0, failed_chunks=[0, 1], fields=[])
    monkeypatch.setattr(pipeline, "extract_document", lambda chunks, **kw: all_failed)

    def must_not_run(chunks, **kw):
        raise AssertionError("risk step must not run")

    monkeypatch.setattr(pipeline, "analyze_document", must_not_run)

    run_id = pipeline.run_pipeline(doc_id, factory)

    with factory() as db:
        run = db.get(AnalysisRun, run_id)
        assert db.get(Document, doc_id).status == "failed"
        assert "no chunk could be analyzed" in run.error


def test_document_without_text_fails(factory, doc_id, monkeypatch):
    monkeypatch.setattr(pipeline, "parse_document", lambda path, file_type: [PageText(1, "", 0)])

    run_id = pipeline.run_pipeline(doc_id, factory)

    with factory() as db:
        assert db.get(Document, doc_id).status == "failed"
        assert "no extractable text" in db.get(AnalysisRun, run_id).error
        assert get_pages(db, doc_id) == []


def test_unknown_document_returns_none(factory):
    assert pipeline.run_pipeline(999, factory) is None


def test_unexpected_error_hides_details(factory, doc_id, monkeypatch):
    def boom(chunks, **kw):
        raise RuntimeError("secret document content")

    monkeypatch.setattr(pipeline, "extract_document", boom)

    run_id = pipeline.run_pipeline(doc_id, factory)

    with factory() as db:
        run = db.get(AnalysisRun, run_id)
        assert db.get(Document, doc_id).status == "failed"
        assert run.error == "RuntimeError"


def test_partial_failure_is_flagged(factory, doc_id, monkeypatch):
    partial = extraction_ok(chunks_total=3, chunks_analyzed=2, failed_chunks=[1])
    patch_models(monkeypatch, partial, risk_result(False))

    run_id = pipeline.run_pipeline(doc_id, factory)

    with factory() as db:
        run = db.get(AnalysisRun, run_id)
        assert run.status == "completed_with_errors"
        assert run.extraction_failed_chunks == [1]
        assert db.get(Document, doc_id).status == "needs_review"