from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models.document_page import DocumentPage
from document_processing.parsers.base import PageText


def save_pages(db: Session, document_id: int, pages: list[PageText]) -> int:
    """Store the text of every page of a document, replacing any previous version."""
    db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
    db.add_all(
        [
            DocumentPage(
                document_id=document_id,
                page_number=page.page_number,
                text=page.text,
                ocr_used=page.ocr_used,
                ocr_confidence=page.ocr_confidence,
            )
            for page in pages
        ]
    )
    db.commit()
    return len(pages)


def get_pages(db: Session, document_id: int) -> list[DocumentPage]:
    return list(
        db.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
    )