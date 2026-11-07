import pymupdf

from document_processing.parsers.pdf_parser import parse_pdf


def make_text_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (72, 100),
        "Frais de tenue de compte: 5 euros par mois\n"
        "Commission d'intervention: 8 euros par operation",
        fontsize=14,
    )
    doc.save(path)


def make_scanned_pdf(path, source_path):
    with pymupdf.open(source_path) as src:
        png = src[0].get_pixmap(dpi=200).tobytes("png")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=png)  # image only, no real text
    doc.save(path)


def test_text_pdf_skips_ocr(tmp_path):
    path = tmp_path / "text.pdf"
    make_text_pdf(path)
    pages = parse_pdf(path)
    assert pages[0].ocr_used is False
    assert "tenue de compte" in pages[0].text


def test_scanned_pdf_uses_ocr(tmp_path):
    text_path = tmp_path / "text.pdf"
    scan_path = tmp_path / "scan.pdf"
    make_text_pdf(text_path)
    make_scanned_pdf(scan_path, text_path)

    pages = parse_pdf(scan_path)

    assert pages[0].ocr_used is True
    assert "tenue de compte" in pages[0].text.lower()
    assert pages[0].ocr_confidence is not None