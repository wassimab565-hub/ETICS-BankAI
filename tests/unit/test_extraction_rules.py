from ai_engine.extraction.rules import apply_rules, dedupe, parse_number, post_process
from ai_engine.extraction.schemas import (
    ExtractedField,
    ExtractionResult,
    FieldSource,
    ValidationStatus,
)


def make_field(name, raw, evidence, label=None, context=""):
    source = FieldSource(
        chunk_index=0,
        page_start=1,
        page_end=1,
        line_start=1,
        line_end=2,
        evidence=evidence,
        context=context,
    )
    return ExtractedField(field_name=name, raw_value=raw, label=label, source=source)


def test_money_is_normalized_with_unit():
    field = apply_rules(
        make_field("account_fee", "2,40", "Actif Par mois 2,40 €", "Tenue de compte")
    )
    assert field.value_number == 2.4
    assert field.unit == "EUR/month"
    assert field.status == ValidationStatus.valid


def test_annual_amount_gets_year_unit():
    field = apply_rules(
        make_field(
            "account_fee", "28,80", "Total des frais annuels 28,80 €", "Tenue de compte"
        )
    )
    assert field.unit == "EUR/year"
    assert field.status == ValidationStatus.valid


def test_gratuit_becomes_zero():
    field = apply_rules(make_field("commission", "0", "Prélèvement SEPA Gratuit"))
    assert field.value_number == 0.0
    assert field.status == ValidationStatus.valid


def test_value_missing_from_evidence_needs_review():
    field = apply_rules(
        make_field("account_fee", "2,40", "Carte Visa Classic Par mois 4,20 €")
    )
    assert field.status == ValidationStatus.needs_review
    assert "value not found in evidence" in field.issues


def test_evidence_about_another_topic_needs_review():
    field = apply_rules(make_field("application_fee", "2,40", "Actif Par mois 2,40 €"))
    assert field.status == ValidationStatus.needs_review
    assert "evidence does not mention the expected topic" in field.issues


def test_reference_number_without_digit_is_rejected():
    field = apply_rules(make_field("reference_number", "CCF", "CCF"))
    assert field.status == ValidationStatus.rejected
    assert any("digit" in issue for issue in field.issues)


def test_duration_in_words():
    field = apply_rules(
        make_field(
            "termination_notice_period",
            "huit jours",
            "moyennant un préavis de huit jours",
        )
    )
    assert field.value_number == 8.0
    assert field.unit == "days"
    assert field.status == ValidationStatus.valid


def test_duration_bare_number_uses_evidence_unit():
    field = apply_rules(
        make_field("termination_notice_period", "8", "un préavis de huit jours")
    )
    assert (field.value_number, field.unit) == (8.0, "days")
    assert field.status == ValidationStatus.valid


def test_long_text_needs_review():
    text = "x" * 250
    field = apply_rules(make_field("termination_conditions", text, text))
    assert field.status == ValidationStatus.needs_review
    assert any("too long" in issue for issue in field.issues)


def test_document_type_must_be_allowed():
    ok = apply_rules(
        make_field("document_type", "fee_schedule", "Document d'information tarifaire")
    )
    bad = apply_rules(make_field("document_type", "weird", "Document"))
    assert ok.status == ValidationStatus.valid
    assert bad.status == ValidationStatus.needs_review


def test_dedupe_keeps_best_status():
    good = apply_rules(
        make_field("account_fee", "2,40", "Actif Par mois 2,40 €", "Tenue de compte")
    )
    worse = good.model_copy(update={"status": ValidationStatus.needs_review})
    kept = dedupe([worse, good])
    assert len(kept) == 1
    assert kept[0].status == ValidationStatus.valid


def test_post_process_removes_duplicates():
    field = make_field("account_fee", "2,40", "Actif Par mois 2,40 €", "Tenue de compte")
    result = ExtractionResult(
        model_name="m", prompt_version="p", fields=[field, field.model_copy()]
    )
    processed = post_process(result)
    assert len(processed.fields) == 1
    assert processed.fields[0].value_number == 2.4
    assert processed.is_complete


def test_parse_number():
    assert parse_number("1 000,50 €") == 1000.5
    assert parse_number("2.4") == 2.4
    assert parse_number("abc") is None

def test_context_lines_count_for_the_topic_check():
    field = apply_rules(
        make_field("account_fee", "2,40", "Actif Par mois 2,40 €", context="Tenue de compte")
    )
    assert field.status == ValidationStatus.valid