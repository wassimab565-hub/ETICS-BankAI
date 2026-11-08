from ai_engine.extraction.schemas import FIELD_KINDS
from ai_engine.prompts.extraction import DOCUMENT_TYPES
from ai_engine.prompts.risk_analysis import RISK_CATEGORIES
from backend.models.analysis import ReviewDecisionValue
from backend.models.document import DocumentStatus
from frontend.components import labels


def test_every_backend_value_has_a_french_label():
    assert set(labels.FIELD_LABELS) == set(FIELD_KINDS)
    assert set(labels.CATEGORY_LABELS) == set(RISK_CATEGORIES)
    assert set(labels.DOCUMENT_TYPE_LABELS) == set(DOCUMENT_TYPES)
    assert set(labels.STATUS_LABELS) == {status.value for status in DocumentStatus}
    assert set(labels.DECISION_LABELS) == {decision.value for decision in ReviewDecisionValue}


def test_priority_label():
    assert labels.priority_label("high") == "🔴 Élevée"
    assert labels.priority_label("low") == "🟢 Faible"
    assert labels.priority_label(None) == "⚪ Non évaluée"


def test_unknown_values_fall_back_to_the_raw_value():
    assert labels.label(labels.STATUS_LABELS, "something_new") == "something_new"
    assert labels.label(labels.STATUS_LABELS, None) == "—"
    assert labels.priority_label("weird") == "⚪ Non évaluée"