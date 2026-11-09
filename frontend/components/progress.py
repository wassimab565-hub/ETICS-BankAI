STAGE_LABELS = {
    "queued": "En attente (une autre analyse est peut-être en cours)",
    "reading": "Lecture du document",
    "extraction": "Extraction des informations",
    "risk": "Recherche des points à examiner",
}

# (start, share) of the progress bar for each stage: a rough estimate, not a measure
STAGE_WEIGHTS = {
    "reading": (0.0, 0.05),
    "extraction": (0.05, 0.60),
    "risk": (0.65, 0.35),
}


def is_final(status: dict) -> bool:
    """True once the analysis is no longer running."""
    return status.get("status") != "processing"


def progress_fraction(status: dict) -> float:
    """Overall progress between 0 and 1, from the stage and the chunk counters."""
    state = status.get("progress") or {}
    weights = STAGE_WEIGHTS.get(state.get("stage"))
    if weights is None:
        return 0.0
    start, share = weights
    total = state.get("total") or 0
    done = min(state.get("done") or 0, total) if total else 0
    ratio = done / total if total else 0.0
    return round(min(start + share * ratio, 1.0), 3)


def progress_text(status: dict) -> str:
    state = status.get("progress") or {}
    stage = state.get("stage")
    text = STAGE_LABELS.get(stage, "Analyse en cours")
    total = state.get("total") or 0
    if stage in ("extraction", "risk") and total:
        text += f" ({state.get('done') or 0}/{total} passages)"
    return text


def outcome(status: dict) -> tuple[str | None, str]:
    """(streamlit message level, text) for a finished analysis, (None, '') otherwise."""
    if status.get("status") == "failed":
        return "error", "L'analyse a échoué."
    if status.get("run_status") == "completed_with_errors":
        return (
            "warning",
            "Analyse terminée, mais certains passages n'ont pas pu être analysés : "
            "les résultats peuvent être incomplets.",
        )
    if status.get("status") == "needs_review":
        return "success", "Analyse terminée : des éléments sont à relire."
    if status.get("status") == "processed":
        return "success", "Analyse terminée."
    return None, ""