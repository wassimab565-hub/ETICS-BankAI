from datetime import timedelta, timezone

from frontend.components.documents_view import documents_to_rows, format_date, format_size


def test_format_size():
    assert format_size(512) == "512 o"
    assert format_size(696064) == "680 Ko"
    assert format_size(1_572_864) == "1,5 Mo"


def test_format_date():
    iso = "2026-11-07T01:15:19.100793Z"
    assert format_date(iso, tz=timezone.utc) == "07/11/2026 01:15"
    assert format_date(iso, tz=timezone(timedelta(hours=1))) == "07/11/2026 02:15"
    assert format_date(None) == "—"
    assert format_date("not a date") == "not a date"


def test_documents_to_rows():
    documents = [
        {
            "id": 1,
            "filename": "dit.pdf",
            "document_type": "fee_schedule",
            "status": "needs_review",
            "review_priority": "low",
            "size_bytes": 696064,
            "uploaded_at": "2026-11-07T01:15:19Z",
        },
        {
            "id": 2,
            "filename": "autre.pdf",
            "document_type": None,
            "status": "uploaded",
            "review_priority": None,
            "size_bytes": 512,
            "uploaded_at": "2026-11-07T02:00:00Z",
        },
    ]

    rows = documents_to_rows(documents, tz=timezone.utc)

    assert rows[0] == {
        "Nom": "dit.pdf",
        "Type": "Tarification",
        "Statut": "À relire",
        "Priorité de revue": "🟢 Faible",
        "Taille": "680 Ko",
        "Téléversé le": "07/11/2026 01:15",
    }
    assert rows[1]["Type"] == "—"
    assert rows[1]["Priorité de revue"] == "⚪ Non évaluée"
    assert rows[1]["Statut"] == "Téléversé"