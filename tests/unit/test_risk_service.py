from ai_engine.chunking.chunker import chunk_pages
from ai_engine.llm.json_client import LLMOutputError
from ai_engine.toxicity import service
from ai_engine.toxicity.schemas import Severity
from ai_engine.validation.llm_schemas import RiskOutput
from document_processing.parsers.base import PageText

CLAUSE = "Nous pouvons résilier l’Offre avec un préavis de deux mois, dès lors que vous ne répondez plus aux critères."


def page(number, text):
    return PageText(number, text, len(text))


def clause_chunk():
    return chunk_pages([page(1, CLAUSE)])[0]


def fake_output(lines):
    return RiskOutput.model_validate(
        {
            "findings": [
                {
                    "category": "termination_changes",
                    "evidence_lines": lines,
                    "impacts_customer": True,
                    "unclear_for_customer": False,
                    "bank_decides_alone": True,
                    "explanation": "  Le préavis est de deux mois.  ",
                    "suggested_action": "Vérifier le critère.",
                }
            ]
        }
    )


def test_analyze_chunk_builds_finding(monkeypatch):
    monkeypatch.setattr(service, "chat_json", lambda *a, **k: (fake_output([1]), {}))

    findings, dropped = service.analyze_chunk(clause_chunk())

    assert dropped == []
    finding = findings[0]
    assert finding.category == "termination_changes"
    assert finding.criteria.bank_decides_alone is True
    assert finding.explanation == "Le préavis est de deux mois."
    assert finding.source.evidence == CLAUSE
    assert finding.severity is None


def test_unusable_lines_are_dropped(monkeypatch):
    monkeypatch.setattr(service, "chat_json", lambda *a, **k: (fake_output([99]), {}))

    findings, dropped = service.analyze_chunk(clause_chunk())

    assert findings == []
    assert dropped[0]["category"] == "termination_changes"


def test_failed_chunk_is_recorded(monkeypatch):
    def boom(*args, **kwargs):
        raise LLMOutputError("bad")

    monkeypatch.setattr(service, "chat_json", boom)

    result = service.analyze_document([clause_chunk()], select=False)

    assert result.failed_chunks == [0]
    assert result.chunks_analyzed == 0
    assert result.is_complete is False


def test_analyze_document_collects_findings(monkeypatch):
    monkeypatch.setattr(service, "chat_json", lambda *a, **k: (fake_output([1]), {}))

    result = service.analyze_document([clause_chunk()], select=False)

    assert len(result.findings) == 1
    assert result.chunks_analyzed == 1
    assert result.is_complete is True
    assert result.prompt_version.startswith("risk_")
    assert result.findings[0].severity != Severity.high


def test_only_selected_chunks_are_sent(monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(1)
        return RiskOutput.model_validate({"findings": []}), {}

    monkeypatch.setattr(service, "chat_json", fake)
    pages = [
        page(1, "Nous pouvons résilier avec un préavis de deux mois."),
        page(2, "Présentation générale du document et de ses annexes."),
    ]
    chunks = chunk_pages(pages, max_chars=80, overlap_chars=0)
    assert len(chunks) == 2

    result = service.analyze_document(chunks)

    assert len(calls) == 1
    assert result.chunks_total == 1