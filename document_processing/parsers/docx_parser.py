from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_processing.parsers.base import PageText


def _has_page_break(paragraph_element) -> bool:
    return any(
        br.get(qn("w:type")) == "page" for br in paragraph_element.iter(qn("w:br"))
    )


def parse_docx(path: str | Path) -> list[PageText]:
    """Extract paragraphs and tables in order, split on explicit page breaks.

    DOCX has no fixed pagination: without page breaks, the whole document is page 1.
    """
    doc = Document(str(path))
    pages: list[PageText] = []
    lines: list[str] = []

    def close_page() -> None:
        text = "\n".join(lines)
        pages.append(
            PageText(page_number=len(pages) + 1, text=text, char_count=len(text.strip()))
        )
        lines.clear()

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            lines.append(Paragraph(child, doc).text)
            if _has_page_break(child):
                close_page()
        elif child.tag == qn("w:tbl"):
            for row in Table(child, doc).rows:
                lines.append(" | ".join(cell.text.strip() for cell in row.cells))

    if any(line.strip() for line in lines) or not pages:
        close_page()
    return pages