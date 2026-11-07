from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class PageText:
    page_number: int  # starts at 1
    text: str
    char_count: int


def parse_pdf(path: str | Path) -> list[PageText]:
    """Extract text page by page, keeping the page number for traceability."""
    pages: list[PageText] = []
    with pymupdf.open(path) as pdf:
        for index, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            pages.append(
                PageText(page_number=index, text=text, char_count=len(text.strip()))
            )
    return pages