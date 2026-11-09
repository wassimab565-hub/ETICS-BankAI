from datetime import datetime, timezone, tzinfo

from frontend.components.labels import (
    DOCUMENT_TYPE_LABELS,
    STATUS_LABELS,
    label,
    priority_label,
)


def format_size(size_bytes: int) -> str:
    """Human-readable size in French units (o, Ko, Mo)."""
    if size_bytes < 1024:
        return f"{size_bytes} o"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} Ko"
    return f"{size_bytes / (1024 * 1024):.1f} Mo".replace(".", ",")


def format_date(value: str | None, tz: tzinfo | None = None) -> str:
    """ISO date from the API (UTC) shown as dd/mm/yyyy hh:mm in the local timezone."""
    if not value:
        return "—"
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz).strftime("%d/%m/%Y %H:%M")


def documents_to_rows(documents: list[dict], tz: tzinfo | None = None) -> list[dict]:
    """Table rows (French column names) for the documents list."""
    return [
        {
            "Nom": doc["filename"],
            "Type": label(DOCUMENT_TYPE_LABELS, doc.get("document_type")),
            "Statut": label(STATUS_LABELS, doc["status"]),
            "Priorité de revue": priority_label(doc.get("review_priority")),
            "Taille": format_size(doc["size_bytes"]),
            "Téléversé le": format_date(doc.get("uploaded_at"), tz),
        }
        for doc in documents
    ]