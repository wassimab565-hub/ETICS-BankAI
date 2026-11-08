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


RISK_ITEM = {
    "category": "termination_changes",
    "evidence_lines": [1],
    "impacts_customer": True,
    "unclear_for_customer": False,
    "bank_decides_alone": True,
    "explanation": "x",
    "suggested_action": "x",
}


def test_risk_schema_rejects_unknown_category():
    with pytest.raises(ValidationError):
        RiskOutput.model_validate({"findings": [{**RISK_ITEM, "category": "foo"}]})


def test_risk_schema_requires_criteria():
    incomplete = {k: v for k, v in RISK_ITEM.items() if k != "bank_decides_alone"}
    with pytest.raises(ValidationError):
        RiskOutput.model_validate({"findings": [incomplete]})
    assert RiskOutput.model_validate({"findings": [RISK_ITEM]}).findings[0].bank_decides_alone


def test_extraction_schema_accepts_number_and_string():
    data = {
        "fields": [
            {"field_name": "interest_rate", "value": 5.2, "unit": "percent", "evidence_lines": [2]},
            {"field_name": "bank_name", "value": "CCF", "unit": None, "evidence_lines": [1]},
        ]
    }
    parsed = ExtractionOutput.model_validate(data)
    assert parsed.fields[0].value == 5.2
    assert parsed.fields[1].value == "CCF"


def test_extraction_schema_requires_value_and_lines():
    no_value = {"fields": [{"field_name": "bank_name", "value": None, "unit": None, "evidence_lines": [1]}]}
    no_lines = {"fields": [{"field_name": "bank_name", "value": "CCF", "unit": None, "evidence_lines": []}]}
    with pytest.raises(ValidationError):
        ExtractionOutput.model_validate(no_value)
    with pytest.raises(ValidationError):
        ExtractionOutput.model_validate(no_lines)

def test_output_schemas_limit_items_for_the_model():
    assert ExtractionOutput.model_json_schema()["properties"]["fields"]["maxItems"] == 30
    assert RiskOutput.model_json_schema()["properties"]["findings"]["maxItems"] == 3