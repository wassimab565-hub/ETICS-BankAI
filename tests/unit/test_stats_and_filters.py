import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models.analysis  # noqa: F401
import backend.models.document_page  # noqa: F401
from backend.main import app
from backend.models.analysis import AnalysisRun, RiskFindingRow
from backend.models.document import Document
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
    yield TestClient(app), factory
    app.dependency_overrides.clear()
    engine.dispose()


def add_doc(factory, name, sha, status="uploaded", priority=None, doc_type=None):
    with factory() as db:
        doc = Document(
            filename=name,
            file_path=f"data/raw/uploads/{sha}.pdf",
            sha256=sha * 64,
            file_type="pdf",
            size_bytes=10,
            status=status,
            review_priority=priority,
            document_type=doc_type,
        )
        db.add(doc)
        db.commit()
        return doc.id


def add_run(factory, doc_id, findings):
    """One analysis run with findings given as (category, severity) pairs."""
    with factory() as db:
        run = AnalysisRun(
            document_id=doc_id,
            model_name="m",
            extraction_prompt_version="e",
            risk_prompt_version="r",
        )
        db.add(run)
        db.flush()
        for category, severity in findings:
            db.add(
                RiskFindingRow(
                    run_id=run.id,
                    category=category,
                    severity=severity,
                    explanation="x",
                    suggested_action="x",
                    criteria={},
                    status="needs_review",
                    chunk_index=0,
                    page_start=1,
                    page_end=1,
                    line_start=1,
                    line_end=1,
                    evidence="e",
                )
            )
        db.commit()


def test_list_filters(env):
    client, factory = env
    add_doc(factory, "dit-tarif.pdf", "a", "needs_review", "low", "fee_schedule")
    add_doc(factory, "contrat.pdf", "b", "processed", "high", "general_terms")
    add_doc(factory, "autre.pdf", "c")

    def names(**params):
        return sorted(d["filename"] for d in client.get("/documents", params=params).json())

    assert len(names()) == 3
    assert names(status="needs_review") == ["dit-tarif.pdf"]
    assert names(review_priority="high") == ["contrat.pdf"]
    assert names(document_type="fee_schedule") == ["dit-tarif.pdf"]
    assert names(q="TARIF") == ["dit-tarif.pdf"]
    assert names(status="processed", q="tarif") == []


def test_stats_counts_only_the_latest_run(env):
    client, factory = env
    first = add_doc(factory, "a.pdf", "a", "needs_review", "high", "fee_schedule")
    second = add_doc(factory, "b.pdf", "b", "processed", "low", "fee_schedule")
    add_doc(factory, "c.pdf", "c")
    add_run(factory, first, [("fairness_balance", "low")])  # old run: ignored
    add_run(factory, first, [("termination_changes", "high"), ("penalties_charges", "low")])
    add_run(factory, second, [])

    body = client.get("/stats").json()

    assert body["documents_total"] == 3
    assert body["documents_by_status"] == {"needs_review": 1, "processed": 1, "uploaded": 1}
    assert body["documents_by_review_priority"] == {"high": 1, "low": 1, "not_assessed": 1}
    assert body["documents_by_type"] == {"fee_schedule": 2, "unknown": 1}
    assert body["documents_with_findings"] == 1
    assert body["findings_by_category"] == {"termination_changes": 1, "penalties_charges": 1}
    assert body["findings_by_severity"] == {"high": 1, "low": 1}
    assert "conformité" in body["notice"]


def test_stats_on_an_empty_database(env):
    client, _ = env
    body = client.get("/stats").json()
    assert body["documents_total"] == 0
    assert body["documents_with_findings"] == 0
    assert body["documents_by_status"] == {}
    assert body["findings_by_category"] == {}