from datetime import timezone

from frontend.components.results_view import (
    analysis_summary,
    clean_optional,
    corrected_value,
    criteria_labels,
    escape_markdown,
    format_value,
    issue_label,
    latest_review,
    order_fields,
    page_text,
    review_progress,
    review_summary,
    severity_label,
    split_findings,
    validate_review,
)


def field(**kwargs):
    base = {
        "id": 1,
        "field_name": "account_fee",
        "raw_value": "2,40",
        "value_number": 2.4,
        "unit": "EUR/month",
        "status": "valid",
        "reviews": [],
    }
    base.update(kwargs)
    return base


def test_format_value_money_and_units():
    assert format_value(field()) == "2,40 € par mois"
    assert format_value(field(value_number=5.0, unit="EUR")) == "5,00 €"
    assert format_value(field(value_number=8.0, unit="EUR/year")) == "8,00 € par an"


def test_format_value_percent_duration_text():
    assert format_value(field(value_number=5.2, unit="percent")) == "5,2 %"
    assert format_value(field(value_number=8.0, unit="days")) == "8 jours"
    assert format_value(field(value_number=2.0, unit="months")) == "2 mois"
    assert format_value(field(value_number=None, unit=None, raw_value="CCF - SA")) == "CCF - SA"
    assert format_value(field(value_number=0.0, unit=None)) == "0"


def test_format_value_thousands_and_unknown_unit():
    assert format_value(field(value_number=1000.5, unit="EUR")) == "1\u00a0000,50 €"
    assert format_value(field(value_number=2.0, unit="foo")) == "2 foo"


def test_escape_markdown():
    assert escape_markdown("*a* [b] $5") == "\\*a\\* \\[b\\] \\$5"
    assert escape_markdown("simple text") == "simple text"


def test_issue_label():
    assert "ligne voisine" in issue_label("value not found in evidence")
    assert "non reconnu" in issue_label("unknown document type 'weird'")
    assert "corrigée" in issue_label("customer can refuse or leave: 'bank decides alone' set to false")
    assert issue_label("something new") == "something new"


def test_criteria_labels():
    criteria = {"impacts_customer": True, "unclear_for_customer": False, "bank_decides_alone": True}
    labels = criteria_labels(criteria)
    assert len(labels) == 2
    assert "banque seule" in labels[1]
    assert criteria_labels({}) == []


def test_page_text_and_severity_label():
    assert page_text({"page_start": 3, "page_end": 3}) == "p. 3"
    assert page_text({"page_start": 3, "page_end": 4}) == "p. 3–4"
    assert severity_label("medium") == "🟠 Moyen"
    assert severity_label(None) == "⚪ Non évalué"


def test_latest_review_and_correction():
    reviews = [
        {"id": 1, "corrected_value": "2,50"},
        {"id": 2, "corrected_value": None},
    ]
    item = field(reviews=reviews)
    assert latest_review(item)["id"] == 2
    assert corrected_value(item) == "2,50"
    assert latest_review(field()) is None
    assert corrected_value(field()) is None


def test_review_summary():
    review = {
        "decision": "confirmed",
        "reviewer_name": "Wassim",
        "reviewed_at": "2026-11-07T01:15:00Z",
        "notes": "ok",
    }
    assert review_summary(review, tz=timezone.utc) == "Confirmé — Wassim, le 07/11/2026 01:15 · ok"
    review["notes"] = None
    assert review_summary(review, tz=timezone.utc) == "Confirmé — Wassim, le 07/11/2026 01:15"


def results_of(findings=(), **run):
    base = {
        "status": "completed",
        "error": None,
        "extraction_failed_chunks": [],
        "risk_failed_chunks": [],
        "risk_chunks_total": 3,
        "risk_chunks_analyzed": 3,
    }
    base.update(run)
    return {"run": base, "findings": list(findings)}


def test_analysis_summary_without_findings():
    assert analysis_summary(results_of(findings=[{"id": 1}])) == []

    (level, text), = analysis_summary(results_of(risk_chunks_total=4, risk_chunks_analyzed=4))
    assert level == "info"
    assert "4 passage(s) analysé(s) sur 4" in text and "conforme" in text

    (level, text), = analysis_summary(results_of(risk_chunks_total=0, risk_chunks_analyzed=0))
    assert level == "info" and "sans risque" in text


def test_analysis_summary_failures():
    messages = analysis_summary(
        results_of(status="completed_with_errors", risk_failed_chunks=[1])
    )
    assert messages[0][0] == "warning" and "1 passage(s)" in messages[0][1]

    messages = analysis_summary(results_of(status="failed", error="RuntimeError"))
    assert messages == [("error", "L'analyse a échoué : RuntimeError")]


def test_order_fields():
    fields = [
        field(id=3, field_name="commission"),
        field(id=2, field_name="document_title"),
        field(id=1, field_name="commission"),
        field(id=4, field_name="unknown_field"),
    ]
    assert [f["id"] for f in order_fields(fields)] == [2, 1, 3, 4]


def test_split_findings():
    findings = [{"severity": "high"}, {"severity": "low"}, {"severity": None}]
    visible, hidden = split_findings(findings, show_low=False)
    assert [f["severity"] for f in visible] == ["high", None] and hidden == 1
    visible, hidden = split_findings(findings, show_low=True)
    assert len(visible) == 3 and hidden == 0

def test_validate_review():
    assert "nom" in validate_review("  ", "confirmed")
    assert "décision" in validate_review("Wassim", None)
    assert "décision" in validate_review("Wassim", "maybe")
    assert validate_review(" Wassim ", "confirmed") is None


def test_clean_optional():
    assert clean_optional("  note ") == "note"
    assert clean_optional("   ") is None
    assert clean_optional(None) is None


def test_review_progress():
    items = [{"reviews": [{"id": 1}]}, {"reviews": []}, {}]
    assert review_progress(items) == (1, 3)
    assert review_progress([]) == (0, 0)