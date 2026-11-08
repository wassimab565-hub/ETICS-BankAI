import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.models.analysis  # noqa: F401
import backend.models.document_page  # noqa: F401
from ai_engine.extraction.schemas import (
    ExtractedField,
    ExtractionResult,
    FieldSource,
    ValidationStatus,
)
from ai_engine.toxicity.schemas import RiskCriteria, RiskFinding, RiskResult, Severity
from backend.models.document import Document
from backend.services import analysis_repository as repo
from backend.services.page_repository import get_pages, save_pages
from database.connection import Base
from document_processing.parsers.base import PageText


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_doc(db):
    doc = Document(
        filename="a.pdf",
        file_path="data/raw/uploads/x.pdf",
        sha256="x" * 64,
        file_type="pdf",
        size_bytes=10,
    )
    db.add(doc)
    db.commit()
    return doc


def make_run(db, doc):
    return repo.create_run(db, doc.id, "qwen3:8b", "extraction_v7", "risk_v5")


def source(evidence="Actif Par mois 2,40 €"):
    return FieldSource(
        chunk_index=2,
        page_start=3,
        page_end=3,
        line_start=5,
        line_end=6,
        evidence=evidence,
        context="Tenue de compte",
    )


def extracted(name="account_fee", status=ValidationStatus.valid, issues=None):
    return ExtractedField(
        field_name=name,
        label="Tenue de compte",
        raw_value="2,40",
        value_number=2.4,
        unit="EUR/month",
        source=source(),
        status=status,
        issues=issues or [],
    )


def finding(severity):
    return RiskFinding(
        category="termination_changes",
        explanation="x",
        suggested_action="x",
        criteria=RiskCriteria(
            impacts_customer=True, unclear_for_customer=True, bank_decides_alone=False
        ),
        model_criteria=RiskCriteria(
            impacts_customer=True, unclear_for_customer=True, bank_decides_alone=True
        ),
        severity=severity,
        source=source("Nous pouvons résilier l’Offre avec un préavis de deux mois."),
    )


def test_save_pages_replaces_existing(db):
    doc = make_doc(db)
    two = [PageText(1, "a", 1), PageText(2, "b", 1, ocr_used=True, ocr_confidence=91.5)]
    assert save_pages(db, doc.id, two) == 2
    assert [p.text for p in get_pages(db, doc.id)] == ["a", "b"]

    save_pages(db, doc.id, [PageText(1, "new", 3)])
    pages = get_pages(db, doc.id)
    assert len(pages) == 1 and pages[0].text == "new"

    save_pages(db, doc.id, two)
    assert get_pages(db, doc.id)[1].ocr_confidence == 91.5


def test_save_extraction_stores_fields_and_stats(db):
    run = make_run(db, make_doc(db))
    result = ExtractionResult(
        model_name="qwen3:8b",
        prompt_version="extraction_v7",
        chunks_total=5,
        chunks_analyzed=4,
        failed_chunks=[3],
        fields=[
            extracted(),
            extracted("reference_number", ValidationStatus.rejected, ["no digit"]),
        ],
    )

    repo.save_extraction(db, run, result)

    assert (run.extraction_chunks_total, run.extraction_chunks_analyzed) == (5, 4)
    assert run.extraction_failed_chunks == [3]
    rows = repo.list_fields(db, run.id)
    assert [r.field_name for r in rows] == ["account_fee", "reference_number"]
    first = rows[0]
    assert (first.raw_value, first.value_number, first.unit) == ("2,40", 2.4, "EUR/month")
    assert (first.page_start, first.line_start, first.chunk_index) == (3, 5, 2)
    assert first.evidence == "Actif Par mois 2,40 €" and first.context == "Tenue de compte"
    assert rows[1].status == "rejected" and rows[1].issues == ["no digit"]


def test_save_risk_stores_findings_and_priority(db):
    doc = make_doc(db)
    run = make_run(db, doc)
    result = RiskResult(
        model_name="qwen3:8b",
        prompt_version="risk_v5",
        chunks_total=2,
        chunks_analyzed=2,
        findings=[finding(Severity.high), finding(Severity.low)],
    )

    repo.save_risk(db, run, result)

    assert run.review_priority == "high"
    rows = repo.list_findings(db, run.id)
    assert [r.severity for r in rows] == ["high", "low"]
    assert rows[0].criteria["bank_decides_alone"] is False
    assert rows[0].model_criteria["bank_decides_alone"] is True

    incomplete = RiskResult(model_name="m", prompt_version="p", failed_chunks=[1])
    other = make_run(db, doc)
    repo.save_risk(db, other, incomplete)
    assert other.review_priority is None
    assert other.risk_failed_chunks == [1]


def test_finish_run_status(db):
    doc = make_doc(db)
    clean = make_run(db, doc)
    repo.finish_run(db, clean)
    assert clean.status == "completed" and clean.finished_at is not None

    partial = make_run(db, doc)
    repo.save_extraction(
        db, partial, ExtractionResult(model_name="m", prompt_version="p", failed_chunks=[3])
    )
    repo.finish_run(db, partial)
    assert partial.status == "completed_with_errors"


def test_fail_run(db):
    run = make_run(db, make_doc(db))
    repo.fail_run(db, run, "OllamaError")
    assert run.status == "failed"
    assert run.error == "OllamaError"
    assert run.finished_at is not None


def test_latest_run(db):
    doc = make_doc(db)
    make_run(db, doc)
    second = make_run(db, doc)
    assert repo.latest_run(db, doc.id).id == second.id
    assert repo.latest_run(db, 999) is None


def test_add_review_validation(db):
    run = make_run(db, make_doc(db))
    repo.save_extraction(
        db, run, ExtractionResult(model_name="m", prompt_version="p", fields=[extracted()])
    )
    repo.save_risk(
        db,
        run,
        RiskResult(model_name="m", prompt_version="p", findings=[finding(Severity.low)]),
    )
    field_id = repo.list_fields(db, run.id)[0].id
    finding_id = repo.list_findings(db, run.id)[0].id

    with pytest.raises(ValueError):  # empty reviewer name
        repo.add_review(db, reviewer_name="  ", decision="confirmed", field_id=field_id)
    with pytest.raises(ValueError):  # unknown decision
        repo.add_review(db, reviewer_name="Wassim", decision="maybe", field_id=field_id)
    with pytest.raises(ValueError):  # no target
        repo.add_review(db, reviewer_name="Wassim", decision="confirmed")
    with pytest.raises(ValueError):  # two targets
        repo.add_review(
            db, reviewer_name="Wassim", decision="confirmed",
            field_id=field_id, finding_id=finding_id,
        )
    with pytest.raises(ValueError):  # a finding cannot be corrected
        repo.add_review(
            db, reviewer_name="Wassim", decision="confirmed",
            finding_id=finding_id, corrected_value="x",
        )
    with pytest.raises(LookupError):  # unknown target
        repo.add_review(db, reviewer_name="Wassim", decision="confirmed", field_id=999)


def test_add_review_stores_correction_next_to_model_value(db):
    run = make_run(db, make_doc(db))
    repo.save_extraction(
        db, run, ExtractionResult(model_name="m", prompt_version="p", fields=[extracted()])
    )
    row = repo.list_fields(db, run.id)[0]

    review = repo.add_review(
        db,
        reviewer_name=" Wassim ",
        decision="confirmed",
        field_id=row.id,
        corrected_value="2,50",
        notes="checked in the PDF",
    )

    assert review.reviewer_name == "Wassim"
    assert review.reviewed_at is not None
    assert row.raw_value == "2,40"  # the model value is untouched
    assert row.reviews[0].corrected_value == "2,50"