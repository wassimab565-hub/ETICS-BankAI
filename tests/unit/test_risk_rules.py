from ai_engine.extraction.schemas import FieldSource
from ai_engine.toxicity.rules import (
    apply_rules,
    compute_severity,
    dedupe,
    post_process,
    review_priority,
)
from ai_engine.toxicity.schemas import (
    RiskCriteria,
    RiskFinding,
    RiskResult,
    Severity,
)

BANK_CLAUSE = "Nous pouvons résilier l’Offre avec un préavis de deux mois."


def make_finding(category="fairness_balance", evidence=BANK_CLAUSE, i=True, u=True, b=True):
    source = FieldSource(
        chunk_index=0,
        page_start=1,
        page_end=1,
        line_start=1,
        line_end=2,
        evidence=evidence,
    )
    return RiskFinding(
        category=category,
        explanation="x",
        suggested_action="x",
        criteria=RiskCriteria(
            impacts_customer=i, unclear_for_customer=u, bank_decides_alone=b
        ),
        source=source,
    )


def with_severity(finding, severity):
    return finding.model_copy(update={"severity": severity})


def result_of(*findings):
    return RiskResult(model_name="m", prompt_version="p", findings=list(findings))


def test_severity_from_criteria():
    assert compute_severity(RiskCriteria(impacts_customer=True, unclear_for_customer=True, bank_decides_alone=True)) == Severity.high
    assert compute_severity(RiskCriteria(impacts_customer=True, unclear_for_customer=False, bank_decides_alone=True)) == Severity.medium
    assert compute_severity(RiskCriteria(impacts_customer=True, unclear_for_customer=False, bank_decides_alone=False)) == Severity.low
    assert compute_severity(RiskCriteria(impacts_customer=False, unclear_for_customer=False, bank_decides_alone=False)) == Severity.low


def test_customer_exit_removes_bank_decides_alone():
    evidence = (
        "Nous pouvons modifier l’Offre à notre initiative. "
        "Si vous refusez la modification, vous pouvez résilier."
    )
    finding = apply_rules(make_finding(evidence=evidence))
    assert finding.criteria.bank_decides_alone is False
    assert finding.model_criteria.bank_decides_alone is True
    assert finding.severity == Severity.medium
    assert any("refuse or leave" in issue for issue in finding.issues)


def test_termination_evidence_without_bank_side_gets_a_warning():
    finding = apply_rules(
        make_finding("termination_changes", "Vous pouvez résilier l’Offre, à tout moment, par écrit.")
    )
    assert any("decision of the bank" in issue for issue in finding.issues)


def test_termination_with_bank_side_has_no_warning():
    finding = apply_rules(make_finding("termination_changes", BANK_CLAUSE))
    assert finding.issues == []
    assert finding.criteria.bank_decides_alone is True


def test_dedupe_keeps_highest_severity():
    high = apply_rules(make_finding())
    low = apply_rules(make_finding(u=False, b=False))
    kept = dedupe([low, high])
    assert len(kept) == 1
    assert kept[0].severity == Severity.high


def test_dedupe_merges_contained_evidence():
    longer = BANK_CLAUSE + " L’Offre prend fin automatiquement."
    kept = dedupe([apply_rules(make_finding()), apply_rules(make_finding(evidence=longer))])
    assert len(kept) == 1


def test_review_priority():
    low = with_severity(make_finding(), Severity.low)
    medium = with_severity(make_finding(), Severity.medium)
    high = with_severity(make_finding(), Severity.high)

    assert review_priority(result_of()) == Severity.low
    incomplete = RiskResult(model_name="m", prompt_version="p", failed_chunks=[1])
    assert review_priority(incomplete) is None
    assert review_priority(result_of(low, high)) == Severity.high
    assert review_priority(result_of(low, medium)) == Severity.medium
    assert review_priority(result_of(low, low, low)) == Severity.medium
    assert review_priority(result_of(low, low)) == Severity.low


def test_post_process_sorts_by_severity():
    low = make_finding(evidence="Premier passage sans lien.", u=False, b=False)
    high = make_finding(evidence="Second passage différent.")
    processed = post_process(result_of(low, high))
    assert [f.severity for f in processed.findings] == [Severity.high, Severity.low]