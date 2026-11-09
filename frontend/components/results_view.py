import re
from datetime import tzinfo

from frontend.components.documents_view import format_date
from frontend.components.labels import DECISION_LABELS, FIELD_LABELS, label

FIELD_STATUS_ICONS = {"valid": "✅", "needs_review": "⚠️", "rejected": "⛔"}
SEVERITY_LABELS = {"low": "🟢 Faible", "medium": "🟠 Moyen", "high": "🔴 Élevé"}

UNIT_TEXT = {
    "EUR": "€",
    "month": "par mois",
    "year": "par an",
    "operation": "par opération",
    "percent": "%",
    "days": "jours",
    "weeks": "semaines",
    "months": "mois",
    "years": "ans",
    "hours": "heures",
}

CRITERIA_LABELS = {
    "impacts_customer": "Impact concret possible sur l'argent ou les droits du client",
    "unclear_for_customer": "Formulation peu claire pour un client ordinaire",
    "bank_decides_alone": "Décision laissée à la banque seule",
}

# Messages produced by the backend rules (English), matched by prefix.
ISSUE_LABELS = (
    ("empty value", "Valeur vide."),
    ("unknown document type", "Type de document non reconnu."),
    ("zero value without", "Valeur nulle sans mention « gratuit » dans le passage."),
    ("value is not a number", "La valeur n'est pas un nombre."),
    (
        "value not found in evidence",
        "La valeur n'apparaît pas dans le passage cité (elle est peut-être sur la ligne voisine).",
    ),
    ("no duration matching", "Aucune durée correspondante dans le passage."),
    ("duration not found", "La durée n'apparaît pas dans le passage cité."),
    ("text too long", "Texte très long : à résumer ou à relire."),
    (
        "reference number without digit",
        "Référence sans chiffre : probablement un nom, pas un numéro.",
    ),
    (
        "evidence does not mention the expected topic",
        "Le passage cité ne mentionne pas le thème attendu pour ce champ.",
    ),
    (
        "customer can refuse or leave",
        "Le client peut refuser ou résilier : « décision de la banque seule » corrigée en non.",
    ),
    (
        "evidence does not show a decision of the bank",
        "Le passage cité ne montre pas clairement une décision de la banque : "
        "vérifiez qu'il correspond à l'explication.",
    ),
)


def _number(value: float, decimals: int | None) -> str:
    """French number: comma decimal, non-breaking space for thousands."""
    if decimals is None:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        text = f"{value:.{decimals}f}"
    integer, _, fraction = text.partition(".")
    integer = f"{int(integer):,}".replace(",", "\u00a0")
    return integer + ("," + fraction if fraction else "")


def format_value(field: dict) -> str:
    """Value of an extracted field as shown to the user ('2,40 € par mois')."""
    number, unit = field.get("value_number"), field.get("unit")
    if number is None:
        return field["raw_value"]
    if not unit:
        return _number(number, None)
    parts = unit.split("/")
    text = _number(number, 2 if parts[0] == "EUR" else None)
    return f"{text} {' '.join(UNIT_TEXT.get(part, part) for part in parts)}"


def escape_markdown(text: str) -> str:
    """Escape model or document text so it is shown as plain text in markdown."""
    return re.sub(r"([\\`*_{}\[\]()#+\-!|>$~])", r"\\\1", text)


def issue_label(issue: str) -> str:
    for prefix, text in ISSUE_LABELS:
        if issue.startswith(prefix):
            return text
    return issue


def criteria_labels(criteria: dict) -> list[str]:
    """French descriptions of the criteria answered 'yes'."""
    return [text for key, text in CRITERIA_LABELS.items() if criteria.get(key)]


def severity_label(severity: str | None) -> str:
    return SEVERITY_LABELS.get(severity, "⚪ Non évalué") if severity else "⚪ Non évalué"


def page_text(item: dict) -> str:
    start, end = item["page_start"], item["page_end"]
    return f"p. {start}" if start == end else f"p. {start}–{end}"


def latest_review(item: dict) -> dict | None:
    reviews = item.get("reviews") or []
    return max(reviews, key=lambda review: review["id"]) if reviews else None


def corrected_value(item: dict) -> str | None:
    """Most recent correction made by a reviewer. The model value itself never changes."""
    corrections = [r for r in item.get("reviews") or [] if r.get("corrected_value")]
    return max(corrections, key=lambda review: review["id"])["corrected_value"] if corrections else None


def review_summary(review: dict, tz: tzinfo | None = None) -> str:
    text = (
        f"{label(DECISION_LABELS, review['decision'])} — {review['reviewer_name']}, "
        f"le {format_date(review['reviewed_at'], tz)}"
    )
    if review.get("notes"):
        text += f" · {review['notes']}"
    return text


def analysis_summary(results: dict) -> list[tuple[str, str]]:
    """Messages (streamlit level, text) about what the analysis covered.

    'Nothing found' is never presented as 'the document is fine'.
    """
    run = results["run"]
    messages: list[tuple[str, str]] = []

    if run["status"] == "failed":
        detail = f" : {run['error']}" if run.get("error") else "."
        messages.append(("error", f"L'analyse a échoué{detail}"))
        return messages

    failed = len(run["extraction_failed_chunks"]) + len(run["risk_failed_chunks"])
    if failed:
        messages.append(
            (
                "warning",
                f"{failed} passage(s) n'ont pas pu être analysés : les résultats peuvent être incomplets.",
            )
        )
    if not results["findings"]:
        total, analyzed = run["risk_chunks_total"], run["risk_chunks_analyzed"]
        if total == 0:
            messages.append(
                (
                    "info",
                    "Aucun passage du document ne contenait de signal à examiner. "
                    "Cela ne signifie pas que le document est sans risque.",
                )
            )
        else:
            messages.append(
                (
                    "info",
                    f"Aucun point à examiner détecté dans les {analyzed} passage(s) analysé(s) sur {total}. "
                    "Cela ne signifie pas que le document est conforme.",
                )
            )
    return messages


def order_fields(fields: list[dict]) -> list[dict]:
    """Fields in the order of the field list, then in order of extraction."""
    order = {name: index for index, name in enumerate(FIELD_LABELS)}
    return sorted(fields, key=lambda f: (order.get(f["field_name"], len(order)), f["id"]))


def split_findings(findings: list[dict], show_low: bool) -> tuple[list[dict], int]:
    """(findings to show, number of low-severity findings hidden)."""
    visible = [f for f in findings if show_low or f.get("severity") != "low"]
    return visible, len(findings) - len(visible)