import json

import pytest
from pydantic import ValidationError

from ai_engine.llm import json_client
from ai_engine.llm.json_client import LLMOutputError, chat_json, parse_json
from ai_engine.validation.llm_schemas import ExtractionOutput, RiskOutput


def fake_chat_factory(contents):
    calls = []

    def fake_chat(prompt, **kwargs):
        calls.append(prompt)
        content = contents[min(len(calls) - 1, len(contents) - 1)]
        return {"content": content, "duration_s": 1.0, "output_tokens": 5}

    return fake_chat, calls


def test_parse_json_plain():
    assert parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_code_fence():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_text_around():
    assert parse_json('Voici le résultat: {"a": 1} Merci.') == {"a": 1}


def test_parse_json_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_json("pas de json ici")


def test_chat_json_retries_then_succeeds(monkeypatch):
    fake, calls = fake_chat_factory(["not json", '{"findings": []}'])
    monkeypatch.setattr(json_client, "chat", fake)

    parsed, meta = chat_json("prompt", RiskOutput)

    assert parsed.findings == []
    assert meta["attempts"] == 2
    assert "invalid" in calls[1]


def test_chat_json_raises_after_max_retries(monkeypatch):
    fake, calls = fake_chat_factory(["bad"])
    monkeypatch.setattr(json_client, "chat", fake)

    with pytest.raises(LLMOutputError):
        chat_json("prompt", RiskOutput)
    assert len(calls) == 3


def test_risk_schema_rejects_unknown_category():
    bad = {
        "findings": [
            {
                "category": "foo",
                "severity": "low",
                "page": 1,
                "evidence": "x",
                "explanation": "x",
                "suggested_action": "x",
            }
        ]
    }
    with pytest.raises(ValidationError):
        RiskOutput.model_validate(bad)


def test_extraction_schema_accepts_number_and_string():
    data = {
        "fields": [
            {"field_name": "interest_rate", "value": 5.2, "unit": "percent", "page": 2, "evidence": "taux 5,2 %"},
            {"field_name": "bank_name", "value": "CCF", "unit": None, "page": 1, "evidence": "CCF"},
        ]
    }
    parsed = ExtractionOutput.model_validate(data)
    assert parsed.fields[0].value == 5.2
    assert parsed.fields[1].value == "CCF"

def test_extraction_schema_requires_value():
    data = {
        "fields": [
            {"field_name": "bank_name", "value": None, "unit": None, "page": 1, "evidence": "CCF"}
        ]
    }
    with pytest.raises(ValidationError):
        ExtractionOutput.model_validate(data)