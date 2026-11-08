from pathlib import Path

from document_processing.parsers.base import PageText
from document_processing.parsers.docx_parser import parse_docx
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.parsers.xlsx_parser import parse_xlsx

PARSERS = {"pdf": parse_pdf, "docx": parse_docx, "xlsx": parse_xlsx}


def parse_document(path: str | Path, file_type: str) -> list[PageText]:
    """Read a document with the parser matching its type (pdf, docx or xlsx)."""
    parser = PARSERS.get(file_type.lower().lstrip("."))
    if parser is None:
        raise ValueError(f"unsupported file type: {file_type}")
    return parser(path)