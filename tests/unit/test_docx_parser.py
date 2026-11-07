from docx import Document

from document_processing.parsers.docx_parser import parse_docx


def test_docx_pages_and_tables(tmp_path):
    path = tmp_path / "sample.docx"
    d = Document()
    d.add_paragraph("Page one text")
    d.add_page_break()
    d.add_paragraph("Page two text")
    table = d.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Frais"
    table.cell(0, 1).text = "5 EUR"
    d.save(path)

    pages = parse_docx(path)

    assert len(pages) == 2
    assert pages[0].page_number == 1 and "Page one" in pages[0].text
    assert "Page two" in pages[1].text
    assert "Frais | 5 EUR" in pages[1].text