from ai_engine.prompts.extraction import (
    EXTRACTION_FIELDS,
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SYSTEM,
    build_extraction_prompt,
)
from ai_engine.prompts.risk_analysis import (
    RISK_CATEGORIES,
    RISK_PROMPT_VERSION,
    RISK_SYSTEM,
    build_risk_prompt,
)

CHUNK = "[Page 3]\n\nLe taux annuel est de 5,2 %."


def test_extraction_prompt_contains_chunk_and_fields():
    prompt = build_extraction_prompt(CHUNK)
    assert f"<document>\n{CHUNK}\n</document>" in prompt
    for name in EXTRACTION_FIELDS:
        assert name in prompt


def test_risk_prompt_contains_chunk_and_categories():
    prompt = build_risk_prompt(CHUNK)
    assert f"<document>\n{CHUNK}\n</document>" in prompt
    for name in RISK_CATEGORIES:
        assert name in prompt
    assert len(RISK_CATEGORIES) == 8


def test_extraction_system_rules():
    text = EXTRACTION_SYSTEM.lower()
    assert "never invent" in text
    assert "untrusted" in text
    assert "evidence_lines" in text


def test_risk_system_rules():
    text = RISK_SYSTEM.lower()
    assert "not a legal judgment" in text
    assert "untrusted" in text
    assert "evidence_lines" in text


def test_prompt_versions_are_defined():
    assert EXTRACTION_PROMPT_VERSION.startswith("extraction_")
    assert RISK_PROMPT_VERSION.startswith("risk_")