STATUS_LABELS = {
    "uploaded": "Téléversé",
    "processing": "Analyse en cours",
    "processed": "Analysé",
    "needs_review": "À relire",
    "failed": "Échec",
}

PRIORITY_LABELS = {
    "low": ("🟢", "Faible"),
    "medium": ("🟠", "Moyenne"),
    "high": ("🔴", "Élevée"),
}
NOT_ASSESSED = ("⚪", "Non évaluée")

DOCUMENT_TYPE_LABELS = {
    "credit_agreement": "Contrat de crédit",
    "account_agreement": "Convention de compte",
    "card_agreement": "Contrat de carte",
    "fee_schedule": "Tarification",
    "general_terms": "Conditions générales",
    "insurance": "Assurance",
    "investment": "Placement / investissement",
    "other": "Autre",
}

FIELD_LABELS = {
    "document_title": "Titre du document",
    "document_type": "Type de document",
    "reference_number": "Numéro de référence",
    "bank_name": "Banque",
    "issue_date": "Date d'émission",
    "effective_date": "Date d'effet",
    "expiry_date": "Date d'expiration",
    "interest_rate": "Taux d'intérêt",
    "application_fee": "Frais de dossier",
    "account_fee": "Frais de tenue de compte / carte",
    "commission": "Commission",
    "late_payment_penalty": "Pénalité de retard",
    "termination_notice_period": "Préavis de résiliation",
    "termination_conditions": "Conditions de résiliation",
}

CATEGORY_LABELS = {
    "transparency": "Transparence",
    "fairness_balance": "Équilibre entre les parties",
    "customer_vulnerability": "Vulnérabilité du client",
    "privacy_data": "Données personnelles",
    "discrimination": "Discrimination",
    "customer_obligations": "Obligations du client",
    "penalties_charges": "Pénalités et frais",
    "termination_changes": "Résiliation et modifications",
}

# "valid" only means that the automatic checks passed, not that the value is proven correct.
FIELD_STATUS_LABELS = {
    "valid": "Contrôles OK",
    "needs_review": "À vérifier",
    "rejected": "Rejeté",
}

DECISION_LABELS = {
    "confirmed": "Confirmé",
    "not_confirmed": "Non confirmé",
    "needs_more_context": "Plus de contexte requis",
}


def label(mapping: dict, key: str | None) -> str:
    """Label of a value, or the raw value when it is unknown (never fails)."""
    if key is None:
        return "—"
    return mapping.get(key, key)


def priority_label(priority: str | None) -> str:
    icon, text = PRIORITY_LABELS.get(priority, NOT_ASSESSED) if priority else NOT_ASSESSED
    return f"{icon} {text}"