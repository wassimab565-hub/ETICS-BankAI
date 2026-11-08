import re

from ai_engine.toxicity.schemas import RiskCriteria, RiskFinding, RiskResult, Severity

# The customer can refuse or leave: the bank does not decide "alone".
CUSTOMER_EXIT = re.compile(
    r"si vous refusez|vous pouvez refuser|vous pouvez r[ée]silier|vous pouvez vous opposer|"
    r"droit de refuser|sans frais|if you refuse|you may terminate|you can terminate",
    re.IGNORECASE,
)
# Wording of a decision taken by the bank.
BANK_SIDE = re.compile(
    r"\bnous (?:pouvons|nous r[ée]servons|avons|sommes|pourrons|serons)\b|\bla banque\b|"
    r"[àa] notre initiative|\bwe may\b|\bthe bank\b",
    re.IGNORECASE,
)

SEVERITY_RANK = {Severity.low: 0, Severity.medium: 1, Severity.high: 2}
LOWS_FOR_MEDIUM = 3


def compute_severity(criteria: RiskCriteria) -> Severity:
    """Severity from the three yes/no answers: 3 yes = high, 2 = medium, 0-1 = low."""
    score = sum(
        [criteria.impacts_customer, criteria.unclear_for_customer, criteria.bank_decides_alone]
    )
    if score == 3:
        return Severity.high
    if score == 2:
        return Severity.medium
    return Severity.low


def apply_rules(finding: RiskFinding) -> RiskFinding:
    """Adjust the model answers with simple text checks and compute the severity."""
    issues = list(finding.issues)
    criteria = finding.criteria
    evidence = finding.source.evidence

    if criteria.bank_decides_alone and CUSTOMER_EXIT.search(evidence):
        criteria = criteria.model_copy(update={"bank_decides_alone": False})
        issues.append("customer can refuse or leave: 'bank decides alone' set to false")

    if finding.category == "termination_changes" and not BANK_SIDE.search(evidence):
        issues.append(
            "evidence does not show a decision of the bank: check that it matches the explanation"
        )

    return finding.model_copy(
        update={
            "criteria": criteria,
            "model_criteria": finding.model_criteria or finding.criteria,
            "severity": compute_severity(criteria),
            "issues": issues,
        }
    )


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _rank(finding: RiskFinding) -> int:
    return SEVERITY_RANK.get(finding.severity, -1)


def dedupe(findings: list[RiskFinding]) -> list[RiskFinding]:
    """Merge findings on the same passage (chunk overlap), keeping the highest severity."""
    kept: list[RiskFinding] = []
    for finding in findings:
        evidence = _norm(finding.source.evidence)
        for index, other in enumerate(kept):
            other_evidence = _norm(other.source.evidence)
            if evidence in other_evidence or other_evidence in evidence:
                if _rank(finding) > _rank(other):
                    kept[index] = finding
                break
        else:
            kept.append(finding)
    return kept


def review_priority(result: RiskResult) -> Severity | None:
    """Review priority of the document. None when it could not be assessed.

    No finding on a complete analysis gives 'low': the interface must say
    'no point detected in the analyzed passages', not 'the document is fine'.
    """
    if not result.findings:
        return Severity.low if result.is_complete else None
    severities = [f.severity for f in result.findings]
    if Severity.high in severities:
        return Severity.high
    if Severity.medium in severities or severities.count(Severity.low) >= LOWS_FOR_MEDIUM:
        return Severity.medium
    return Severity.low


def post_process(result: RiskResult) -> RiskResult:
    """Apply the rules, merge duplicates and sort by severity then page."""
    findings = dedupe([apply_rules(f) for f in result.findings])
    findings.sort(key=lambda f: (-_rank(f), f.source.page_start))
    return result.model_copy(update={"findings": findings})