import pytest
from fastapi.testclient import TestClient
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
from backend.api import analysis as analysis_api
from backend.main import app
from backend.models.document import Document
from backend.services import analysis_repository as repo
from backend.services import pipeline, progress
from database.connection import Base, get_db


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app), factory  # no "with": the startup code is not run
    app.dependency_overrides.clear()
    engine.dispose()


def add_document(factory, status="uploaded"):
    with factory() as db:
        doc = Document(
            filename="a.pdf",
            file_path="data/raw/uploads/x.pdf",
            sha256="x" * 64,
            file_type="pdf",
            size_bytes=10,
            status=status,
        )
        db.add(doc)
        db.commit()
        return doc.id


def source():
    return FieldSource(
        chunk_index=0,
        page_start=2,
        page_end=2,
        line_start=1,
        line_end=2,
        evidence="Actif Par mois 2,40 €",
    )


def seed_analysis(factory, doc_id, finish=True):
    """A finished analysis with one field and one finding."""
    with factory() as db:
        run = repo.create_run(db, doc_id, "qwen3:8b", "extraction_v7", "risk_v5")
        field = ExtractedField(
            field_name="account_fee",
            raw_value="2,40",
            value_number=2.4,
            unit="EUR/month",
            source=source(),
            status=ValidationStatus.valid,
        )
        finding = RiskFinding(
            category="termination_changes",
            explanation="x",
            suggested_action="x",
            criteria=RiskCriteria(
                impacts_customer=True, unclear_for_customer=True, bank_decides_alone=False
            ),
            model_criteria=RiskCriteria(
                impacts_customer=True, unclear_for_customer=True, bank_decides_alone=True
            ),
            severity=Severity.medium,
            source=source(),
        )
        repo.save_extraction(
            db,
            run,
            ExtractionResult(
                model_name="m", prompt_version="p", chunks_total=1, chunks_analyzed=1, fields=[field]
            ),
        )
        repo.save_risk(
            db,
            run,
            RiskResult(
                model_name="m", prompt_version="p", chunks_total=1, chunks_analyzed=1, findings=[finding]
            ),
        )
        if finish:
            repo.finish_run(db, run)
        return run.id


def test_analyze_unknown_document(env):
    client, _ = env
    assert client.post("/documents/999/analyze").status_code == 404


def test_analyze_starts_the_pipeline_in_background(env, monkeypatch):
    client, factory = env
    calls = []
    monkeypatch.setattr(analysis_api, "run_pipeline", lambda document_id: calls.append(document_id))
    doc_id = add_document(factory)

    response = client.post(f"/documents/{doc_id}/analyze")

    assert response.status_code == 202
    assert response.json()["status"] == "processing"
    assert calls == [doc_id]
    with factory() as db:
        assert db.get(Document, doc_id).status == "processing"


def test_analyze_twice_is_refused(env, monkeypatch):
    client, factory = env
    calls = []
    monkeypatch.setattr(analysis_api, "run_pipeline", lambda document_id: calls.append(document_id))
    doc_id = add_document(factory)

    assert client.post(f"/documents/{doc_id}/analyze").status_code == 202
    assert client.post(f"/documents/{doc_id}/analyze").status_code == 409
    assert len(calls) == 1


def test_status_shows_progress_or_queued(env):
    client, factory = env
    doc_id = add_document(factory, status="processing")

    assert client.get(f"/documents/{doc_id}/status").json()["progress"]["stage"] == "queued"

    progress.update(doc_id, "extraction", 3, 10)
    try:
        body = client.get(f"/documents/{doc_id}/status").json()
    finally:
        progress.clear(doc_id)
    assert body["progress"] == {"stage": "extraction", "done": 3, "total": 10}
    assert body["status"] == "processing"


def test_results_before_any_analysis(env):
    client, factory = env
    doc_id = add_document(factory)
    assert client.get(f"/documents/{doc_id}/results").status_code == 404


def test_results_while_running(env):
    client, factory = env
    doc_id = add_document(factory, status="processing")
    with factory() as db:
        repo.create_run(db, doc_id, "m", "e", "r")  # status: running
    assert client.get(f"/documents/{doc_id}/results").status_code == 409


def test_results_content(env):
    client, factory = env
    doc_id = add_document(factory, status="needs_review")
    run_id = seed_analysis(factory, doc_id)

    body = client.get(f"/documents/{doc_id}/results").json()

    assert body["run"]["id"] == run_id
    assert body["run"]["review_priority"] == "medium"
    assert body["analysis_complete"] is True
    assert "avis juridique" in body["notice"]
    field = body["fields"][0]
    assert (field["field_name"], field["raw_value"], field["page_start"]) == ("account_fee", "2,40", 2)
    assert field["evidence"] == "Actif Par mois 2,40 €" and field["reviews"] == []
    finding = body["findings"][0]
    assert finding["severity"] == "medium"
    assert finding["criteria"]["bank_decides_alone"] is False
    assert finding["model_criteria"]["bank_decides_alone"] is True


def test_results_of_a_failed_run(env):
    client, factory = env
    doc_id = add_document(factory, status="failed")
    with factory() as db:
        run = repo.create_run(db, doc_id, "m", "e", "r")
        repo.fail_run(db, run, "RuntimeError")

    body = client.get(f"/documents/{doc_id}/results").json()

    assert body["analysis_complete"] is False
    assert body["run"]["error"] == "RuntimeError"
    assert body["fields"] == [] and body["findings"] == []


def test_review_a_field_keeps_the_model_value(env):
    client, factory = env
    doc_id = add_document(factory, status="needs_review")
    seed_analysis(factory, doc_id)
    field_id = client.get(f"/documents/{doc_id}/results").json()["fields"][0]["id"]

    response = client.post(
        f"/fields/{field_id}/review",
        json={
            "reviewer_name": "Wassim",
            "decision": "confirmed",
            "corrected_value": "2,50",
            "notes": "checked in the PDF",
        },
    )

    assert response.status_code == 201
    assert response.json()["decision"] == "confirmed"
    field = client.get(f"/documents/{doc_id}/results").json()["fields"][0]
    assert field["raw_value"] == "2,40"
    assert field["reviews"][0]["corrected_value"] == "2,50"
    assert field["reviews"][0]["reviewer_name"] == "Wassim"


def test_review_validation_errors(env):
    client, factory = env
    doc_id = add_document(factory, status="needs_review")
    seed_analysis(factory, doc_id)
    field_id = client.get(f"/documents/{doc_id}/results").json()["fields"][0]["id"]

    bad_decision = {"reviewer_name": "Wassim", "decision": "maybe"}
    no_name = {"reviewer_name": "  ", "decision": "confirmed"}
    assert client.post(f"/fields/{field_id}/review", json=bad_decision).status_code == 422
    assert client.post(f"/fields/{field_id}/review", json=no_name).status_code == 422
    assert client.post("/fields/999/review", json={"reviewer_name": "W", "decision": "confirmed"}).status_code == 404


def test_review_a_finding(env):
    client, factory = env
    doc_id = add_document(factory, status="needs_review")
    seed_analysis(factory, doc_id)
    finding_id = client.get(f"/documents/{doc_id}/results").json()["findings"][0]["id"]

    response = client.post(
        f"/findings/{finding_id}/review",
        json={"reviewer_name": "Wassim", "decision": "not_confirmed", "notes": "clause standard"},
    )

    assert response.status_code == 201
    finding = client.get(f"/documents/{doc_id}/results").json()["findings"][0]
    assert finding["reviews"][0]["decision"] == "not_confirmed"
    assert client.post("/findings/999/review", json={"reviewer_name": "W", "decision": "confirmed"}).status_code == 404


def test_recover_interrupted_analyses(env):
    _, factory = env
    doc_id = add_document(factory, status="processing")
    with factory() as db:
        run_id = repo.create_run(db, doc_id, "m", "e", "r").id

    assert pipeline.recover_interrupted(factory) == 1

    with factory() as db:
        assert db.get(Document, doc_id).status == "failed"
        run = repo.get_run(db, run_id)
        assert run.status == "failed" and "restart" in run.error