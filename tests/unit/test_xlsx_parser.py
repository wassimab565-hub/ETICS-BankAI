from openpyxl import Workbook

from document_processing.parsers.xlsx_parser import parse_xlsx


def test_xlsx_sheets_as_pages(tmp_path):
    path = tmp_path / "sample.xlsx"
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Tarifs"
    ws1.append(["Frais", "Montant"])
    ws1.append(["Tenue de compte", 5])
    ws1.append([None, None])
    ws2 = wb.create_sheet("Vide")
    wb.save(path)

    pages = parse_xlsx(path)

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "[Sheet: Tarifs]" in pages[0].text
    assert "Tenue de compte | 5" in pages[0].text
    assert pages[1].char_count == 0