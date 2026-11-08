import re

from ai_engine.extraction.schemas import (
    FIELD_KINDS,
    ExtractedField,
    ExtractionResult,
    ValidationStatus,
    ValueKind,
)
from ai_engine.prompts.extraction import DOCUMENT_TYPES
from ai_engine.validation.evidence import duration_in, value_in_evidence

MAX_TEXT_LENGTH = 200

_NUMBER = re.compile(r"\d+(?:[\s\u00a0]\d{3})*(?:[.,]\d+)?")
_FREE = re.compile(
    r"\b(gratuit(?:e|es|s)?|free|offert(?:e|es|s)?|exon[ée]r[ée]e?s?)\b", re.IGNORECASE
)
_CURRENCY = re.compile(r"€|\beuros?\b|\beur\b", re.IGNORECASE)
_PERIODS = (
    (re.compile(r"par mois|mensuel|/mois|per month", re.IGNORECASE), "month"),
    (re.compile(r"par an|annuel|/an\b|per year", re.IGNORECASE), "year"),
    (re.compile(r"par op[ée]ration|per transaction", re.IGNORECASE), "operation"),
)

# The evidence of a field should mention at least one of these words (heuristic).
FIELD_HINTS = {
    "application_fee": re.compile(
        r"dossier|ouverture|mise en place|souscription|adh[ée]sion|opening|application",
        re.IGNORECASE,
    ),
    "account_fee": re.compile(
        r"tenue de compte|cotisation|abonnement|carte|forfait|account|maintenance",
        re.IGNORECASE,
    ),
    "commission": re.compile(
        r"commission|frais|virement|retrait|pr[ée]l[èe]vement|op[ée]ration|ch[èe]que|fee|charge",
        re.IGNORECASE,
    ),
    "late_payment_penalty": re.compile(
        r"retard|p[ée]nalit|impay|d[ée]couvert|late|penalt", re.IGNORECASE
    ),
    "interest_rate": re.compile(r"taux|taeg|teg|int[ée]r[êe]t|rate|%", re.IGNORECASE),
    "termination_notice_period": re.compile(
        r"pr[ée]avis|notice|r[ée]sili|terminat", re.IGNORECASE
    ),
}

STATUS_RANK = {
    ValidationStatus.valid: 0,
    ValidationStatus.needs_review: 1,
    ValidationStatus.rejected: 2,
}


def parse_number(text: str) -> float | None:
    """First number of a text. A comma means decimal ('2,40' -> 2.4); a dot too ('2.4')."""
    match = _NUMBER.search(text)
    if not match:
        return None
    token = re.sub(r"\s", "", match.group())
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def _find_value_span(evidence: str, value: float) -> tuple[int, int] | None:
    for match in _NUMBER.finditer(evidence):
        parsed = parse_number(match.group())
        if parsed is not None and abs(parsed - value) < 1e-9:
            return match.start(), match.end()
    return None


def detect_unit(kind: ValueKind, evidence: str, value: float | None) -> str | None:
    """Unit read from the evidence: 'EUR/month', 'EUR/year', 'percent'..."""
    if kind == ValueKind.percent:
        return "percent" if "%" in evidence else None
    if kind != ValueKind.money:
        return None

    currency = "EUR" if _CURRENCY.search(evidence) else None
    period = None
    span = _find_value_span(evidence, value) if value is not None else None
    if span:
        window = evidence[max(0, span[0] - 45) : span[1] + 12]
        best = None
        for pattern, name in _PERIODS:
            for match in pattern.finditer(window):
                if best is None or match.start() > best[0]:
                    best = (match.start(), name)  # the period closest to the number
        period = best[1] if best else None
    parts = [part for part in (currency, period) if part]
    return "/".join(parts) if parts else None


def apply_rules(field: ExtractedField) -> ExtractedField:
    """Normalize the value and set the status of one extracted field."""
    kind = FIELD_KINDS[field.field_name]
    evidence = field.source.evidence
    raw = field.raw_value.strip()
    issues: list[str] = []
    rejected = False
    number: float | None = None
    unit = field.unit

    if not raw:
        issues.append("empty value")
        rejected = True
    elif kind == ValueKind.classification:
        if raw.lower() not in DOCUMENT_TYPES:
            issues.append(f"unknown document type '{raw}'")
    elif kind in (ValueKind.money, ValueKind.percent):
        if _FREE.search(raw) or parse_number(raw) == 0.0:
            number = 0.0
            if not _FREE.search(evidence):
                issues.append("zero value without 'gratuit' in the evidence")
        else:
            number = parse_number(raw)
            if number is None:
                issues.append("value is not a number")
            elif not value_in_evidence(number, evidence):
                issues.append("value not found in evidence")
        unit = detect_unit(kind, evidence, number) or field.unit
    elif kind == ValueKind.duration:
        parsed = duration_in(raw)
        if parsed is None:
            from_evidence = duration_in(evidence)
            raw_number = parse_number(raw)
            if from_evidence and (
                raw_number is None or abs(raw_number - from_evidence[0]) < 1e-9
            ):
                parsed = from_evidence
        if parsed:
            number, unit = parsed
            if not value_in_evidence(number, evidence):
                issues.append("duration not found in evidence")
        else:
            issues.append("no duration matching the value")
    else:  # text and date
        if len(raw) > MAX_TEXT_LENGTH:
            issues.append("text too long: summarize or review")
        if not value_in_evidence(raw, evidence):
            issues.append("value not found in evidence")

    if field.field_name == "reference_number" and raw and not re.search(r"\d", raw):
        issues.append("reference number without digit (probably a name)")
        rejected = True

    hint = FIELD_HINTS.get(field.field_name)
    if hint and not hint.search(f"{evidence} {field.label or ''}"):
        issues.append("evidence does not mention the expected topic")

    if rejected:
        status = ValidationStatus.rejected
    elif issues:
        status = ValidationStatus.needs_review
    else:
        status = ValidationStatus.valid
    return field.model_copy(
        update={
            "value_number": number,
            "unit": unit,
            "status": status,
            "issues": field.issues + issues,
        }
    )


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def dedupe(fields: list[ExtractedField]) -> list[ExtractedField]:
    """Remove duplicates (same field, value and evidence), keeping the best status."""
    best: dict[tuple, ExtractedField] = {}
    for field in fields:
        value = field.value_number if field.value_number is not None else _norm(field.raw_value)
        key = (field.field_name, value, _norm(field.source.evidence))
        current = best.get(key)
        if current is None or STATUS_RANK[field.status] < STATUS_RANK[current.status]:
            best[key] = field
    return list(best.values())


def post_process(result: ExtractionResult) -> ExtractionResult:
    """Apply the rules to every field and remove duplicates."""
    processed = [apply_rules(field) for field in result.fields]
    return result.model_copy(update={"fields": dedupe(processed)})