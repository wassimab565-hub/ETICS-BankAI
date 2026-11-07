from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.document import Document


def register_document(
    db: Session, filename: str, ext: str, size_bytes: int, stored: dict
) -> tuple[Document, bool]:
    """Create the document record, or return the existing one if the hash is known."""
    existing = db.scalar(select(Document).where(Document.sha256 == stored["sha256"]))
    if existing:
        return existing, True

    doc = Document(
        filename=filename,
        file_path=stored["stored_path"],
        sha256=stored["sha256"],
        file_type=ext.lstrip("."),
        size_bytes=size_bytes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc, False