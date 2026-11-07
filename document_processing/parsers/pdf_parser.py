from pathlib import Path

import pymupdf

from document_processing.ocr.ocr_engine import ocr_page
from document_processing.parsers.base import PageText

MIN_CHARS_FOR_TEXT = 50


def parse_pdf(
    path: str | Path, ocr: bool = True, min_chars: int = MIN_CHARS_FOR_TEXT
) -> list[PageText]:
    """Extract text page by page. Pages with almost no text are sent to OCR."""
    pages: list[PageText] = []
    with pymupdf.open(path) as pdf:
        for index, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            ocr_used = False
            confidence = None
            if ocr and len(text.strip()) < min_chars:
                text, confidence = ocr_page(page)
                ocr_used = True
            pages.append(
                PageText(
                    page_number=index,
                    text=text,
                    char_count=len(text.strip()),
                    ocr_used=ocr_used,
                    ocr_confidence=confidence,
                )
            )
    return pages