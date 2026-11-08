import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.analysis import (
    AnalysisRun,
    ExtractedFieldRow,
    ReviewDecision,
    RiskFindingRow,
)
from backend.models.document import Document
from backend.models.document_page import DocumentPage
from database.connection import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_run(db):
    doc = Document(
        filename="a.pdf",
        file_path="data/raw/uploads/x.pdf",
        sha256="x" * 64,
        file_type="pdf",
        size_bytes=10,
    )
    db.add(doc)
    db.flush()
    run = AnalysisRun(
        document_id=doc.id,
        model_name="qwen3:8b",
        extraction_prompt_version="extraction_v7",
        risk_prompt_version="risk_v5",
    )
    db.add(run)
    db.flush()
    return doc, run


def make_field(run_id):
    return ExtractedFieldRow(
        run_id=run_id,
        field_name="account_fee",
        raw_value="2,40",
        status="valid",
        chunk_index=0,
        page_start=1,
        page_end=1,
        line_start=1,
        line_end=2,
        evidence="Actif Par mois 2,40 €",
    )


def make_finding(run_id):
    return RiskFindingRow(
        run_id=run_id,
        category="termination_changes",
        severity="medium",
        explanation="x",
        suggested_action="x",
        criteria={"impacts_customer": True, "unclear_for_customer": True, "bank_decides_alone": False},
        model_criteria={"impacts_customer": True, "unclear_for_customer": True, "bank_decides_alone": True},
        status="needs_review",
        chunk_index=0,
        page_start=1,
        page_end=1,
        line_start=1,
        line_end=2,
        evidence="Nous pouvons résilier l’Offre avec un préavis de deux mois.",
    )


def test_all_tables_are_registered():
    expected = {
        "documents",
        "document_pages",
        "analysis_runs",
        "extracted_fields",
        "risk_findings",
        "review_decisions",
    }
    assert expected <= set(Base.metadata.tables)


def test_run_defaults(db):
    _, run = make_run(db)
    assert run.status == "running"
    assert run.extraction_failed_chunks == []
    assert run.risk_failed_chunks == []
    assert run.started_at is not None
    assert run.finished_at is None


def test_run_keeps_its_results(db):
    _, run = make_run(db)
    run.fields.append(make_field(run.id))
    run.findings.append(make_finding(run.id))
    db.commit()

    loaded = db.scalar(select(AnalysisRun))
    assert len(loaded.fields) == 1
    assert len(loaded.findings) == 1
    assert loaded.findings[0].model_criteria["bank_decides_alone"] is True
    assert loaded.findings[0].criteria["bank_decides_alone"] is False


def test_review_needs_exactly_one_target(db):
    _, run = make_run(db)
    field, finding = make_field(run.id), make_finding(run.id)
    db.add_all([field, finding])
    db.flush()

    with pytest.raises(IntegrityError):  # no target
        db.add(ReviewDecision(decision="confirmed", reviewer_name="Wassim"))
        db.flush()
    db.rollback()


def test_review_with_both_targets_is_rejected(db):
    _, run = make_run(db)
    field, finding = make_field(run.id), make_finding(run.id)
    db.add_all([field, finding])
    db.flush()

    with pytest.raises(IntegrityError):
        db.add(
            ReviewDecision(
                field_id=field.id,
                finding_id=finding.id,
                decision="confirmed",
                reviewer_name="Wassim",
            )
        )
        db.flush()
    db.rollback()


def test_correction_does_not_change_model_value(db):
    _, run = make_run(db)
    field = make_field(run.id)
    db.add(field)
    db.flush()
    db.add(
        ReviewDecision(
            field_id=field.id,
            decision="confirmed",
            corrected_value="2,50",
            reviewer_name="Wassim",
        )
    )
    db.commit()

    loaded = db.scalar(select(ExtractedFieldRow))
    assert loaded.raw_value == "2,40"
    assert loaded.reviews[0].corrected_value == "2,50"
    assert loaded.reviews[0].reviewed_at is not None


def test_deleting_a_run_deletes_results_and_reviews(db):
    _, run = make_run(db)
    field = make_field(run.id)
    run.fields.append(field)
    run.findings.append(make_finding(run.id))
    db.flush()
    db.add(ReviewDecision(field_id=field.id, decision="confirmed", reviewer_name="Wassim"))
    db.commit()

    db.delete(run)
    db.commit()

    assert db.scalars(select(ExtractedFieldRow)).all() == []
    assert db.scalars(select(RiskFindingRow)).all() == []
    assert db.scalars(select(ReviewDecision)).all() == []


def test_one_page_number_per_document(db):
    doc, _ = make_run(db)
    db.add(DocumentPage(document_id=doc.id, page_number=1, text="a"))
    db.flush()

    with pytest.raises(IntegrityError):
        db.add(DocumentPage(document_id=doc.id, page_number=1, text="b"))
        db.flush()
    db.rollback()