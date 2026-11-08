from ai_engine.chunking.chunker import chunk_pages
from ai_engine.extraction import service
from ai_engine.extraction.chunk_selector import select_chunks
from ai_engine.extraction.schemas import ValidationStatus
from ai_engine.llm.json_client import LLMOutputError
from ai_engine.validation.llm_schemas import ExtractionOutput
from document_processing.parsers.base import PageText


def page(number, text):
    return PageText(number, text, len(text))


def table_chunk():
    text = "Tenue de compte\nActif\nPar mois\n2,40 €"
    return chunk_pages([page(1, text)])[0]


def fake_output(lines, value=2.4, label="Tenue de compte"):
    return ExtractionOutput.model_validate(
        {
            "fields": [
                {
                    "field_name": "account_fee",
                    "value": value,
                    "unit": None,
                    "label": label,
                    "evidence_lines": lines,
                }
            ]
        }
    )


def test_extract_from_chunk_builds_field(monkeypatch):
    monkeypatch.setattr(service, "chat_json", lambda *a, **k: (fake_output([1, 4]), {}))

    fields, dropped = service.extract_from_chunk(table_chunk())

    assert dropped == []
    field = fields[0]
    assert field.field_name == "account_fee"
    assert field.raw_value == "2.4"
    assert field.label == "Tenue de compte"
    assert field.source.evidence == "Tenue de compte Actif Par mois 2,40 €"
    assert field.status == ValidationStatus.needs_review


def test_unusable_lines_are_dropped(monkeypatch):
    monkeypatch.setattr(service, "chat_json", lambda *a, **k: (fake_output([99]), {}))

    fields, dropped = service.extract_from_chunk(table_chunk())

    assert fields == []
    assert dropped[0]["field_name"] == "account_fee"
    assert "unknown" in dropped[0]["reason"]


def test_failed_chunk_is_recorded(monkeypatch):
    def boom(*args, **kwargs):
        raise LLMOutputError("bad")

    monkeypatch.setattr(service, "chat_json", boom)

    result = service.extract_document([table_chunk()], select=False)

    assert result.failed_chunks == [0]
    assert result.chunks_analyzed == 0
    assert result.is_complete is False


def test_extract_document_collects_fields(monkeypatch):
    monkeypatch.setattr(service, "chat_json", lambda *a, **k: (fake_output([1, 4]), {}))

    result = service.extract_document([table_chunk()], select=False)

    assert len(result.fields) == 1
    assert result.chunks_analyzed == 1
    assert result.is_complete is True
    assert result.prompt_version.startswith("extraction_")


def test_select_chunks_keeps_first_and_keyword_chunks():
    pages = [
        page(1, "Presentation generale du document sans chiffre utile"),
        page(2, "Paragraphe neutre qui parle de la vie de la banque"),
        page(3, "Les frais de tenue de compte sont de 5 euros par mois"),
    ]
    chunks = chunk_pages(pages, max_chars=60, overlap_chars=0)
    assert len(chunks) == 3
    assert select_chunks(chunks) == [0, 2]


def test_select_chunks_empty():
    assert select_chunks([]) == []

def test_context_holds_preceding_lines(monkeypatch):
    text = "Tenue de compte\nActif Par mois 2,40 €"
    chunk = chunk_pages([page(1, text)])[0]
    monkeypatch.setattr(service, "chat_json", lambda *a, **k: (fake_output([2]), {}))

    fields, _ = service.extract_from_chunk(chunk)

    assert fields[0].source.evidence == "Actif Par mois 2,40 €"
    assert fields[0].source.context == "Tenue de compte"