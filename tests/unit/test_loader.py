import pymupdf
import pytest
from docx import Document as WordDocument

from document_processing.loader import parse_document


def test_unsupported_type_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        parse_document(tmp_path / "a.txt", "txt")


def test_docx_goes_to_the_docx_parser(tmp_path):
    path = tmp_path / "a.docx"
    doc = WordDocument()
    doc.add_paragraph("Frais de tenue de compte")
    doc.save(path)
    pages = parse_document(path, "docx")
    assert "Frais de tenue de compte" in pages[0].text


def test_pdf_goes_to_the_pdf_parser(tmp_path):
    path = tmp_path / "a.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_text(
        (72, 100),
        "Frais de tenue de compte: 5 euros par mois\nCommission d'intervention: 8 euros par operation",
        fontsize=14,
    )
    pdf.save(path)
    pages = parse_document(path, ".PDF")
    assert pages[0].page_number == 1
    assert "tenue de compte" in pages[0].text