import pytest
from pydantic import ValidationError

from ai_engine.extraction.schemas import FieldSource, ValidationStatus
from ai_engine.toxicity.schemas import RiskCriteria, RiskFinding, RiskResult


def make_finding(category="termination_changes"):
    source = FieldSource(
        chunk_index=0,
        page_start=1,
        page_end=1,
        line_start=1,
        line_end=2,
        evidence="Nous pouvons résilier l’Offre avec un préavis de deux mois.",
    )
    return RiskFinding(
        category=category,
        explanation="x",
        suggested_action="x",
        criteria=RiskCriteria(
            impacts_customer=True, unclear_for_customer=False, bank_decides_alone=True
        ),
        source=source,
    )


def test_unknown_category_is_rejected():
    with pytest.raises(ValidationError):
        make_finding("foo")


def test_new_finding_defaults():
    finding = make_finding()
    assert finding.severity is None
    assert finding.status == ValidationStatus.needs_review
    assert finding.issues == []


def test_risk_result_is_complete():
    assert RiskResult(model_name="m", prompt_version="p").is_complete is True
    assert RiskResult(model_name="m", prompt_version="p", failed_chunks=[2]).is_complete is False