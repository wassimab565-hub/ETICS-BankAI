import pytest
from pydantic import ValidationError

from ai_engine.extraction.schemas import (
    FIELD_KINDS,
    ExtractedField,
    ExtractionResult,
    FieldSource,
    ValidationStatus,
)
from ai_engine.prompts.extraction import EXTRACTION_FIELDS


def make_field(name="account_fee", **kwargs):
    source = FieldSource(
        chunk_index=0,
        page_start=1,
        page_end=1,
        line_start=1,
        line_end=2,
        evidence="Tenue de compte Actif Par mois 2,40 €",
    )
    return ExtractedField(field_name=name, raw_value="2,40", source=source, **kwargs)


def test_field_kinds_match_prompt_fields():
    assert set(FIELD_KINDS) == set(EXTRACTION_FIELDS)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        make_field("foo")


def test_new_field_needs_review_by_default():
    field = make_field()
    assert field.status == ValidationStatus.needs_review
    assert field.issues == []


def test_missing_fields_ignores_rejected_ones():
    result = ExtractionResult(
        model_name="qwen3:8b",
        prompt_version="extraction_v6",
        fields=[
            make_field("account_fee", status=ValidationStatus.valid),
            make_field("commission", status=ValidationStatus.rejected),
        ],
    )
    missing = result.missing_fields()
    assert "account_fee" not in missing
    assert "commission" in missing


def test_is_complete_false_when_a_chunk_failed():
    result = ExtractionResult(
        model_name="qwen3:8b", prompt_version="extraction_v6", failed_chunks=[3]
    )
    assert result.is_complete is False
    assert ExtractionResult(model_name="m", prompt_version="p").is_complete is True