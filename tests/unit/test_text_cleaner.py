from document_processing.parsers.base import PageText
from document_processing.preprocessing.text_cleaner import clean_pages, clean_text


def test_normalizes_spaces_and_ligatures():
    raw = "Frais\u00a0de  tenue\u202fde compte \ufb01nal"
    assert clean_text(raw) == "Frais de tenue de compte final"


def test_joins_words_split_by_line_break_hyphen():
    assert clean_text("la conven-\ntion est valable") == "la convention est valable"


def test_keeps_hyphen_before_uppercase():
    assert "Jean-\nJaurès" in clean_text("Rue Jean-\nJaurès")


def test_collapses_blank_lines():
    assert clean_text("A\n\n\n\nB   \n") == "A\n\nB"


def test_clean_pages_keeps_page_info():
    pages = [PageText(2, "  Hello\u00a0 world  ", 20, ocr_used=True, ocr_confidence=90.0)]
    result = clean_pages(pages)
    assert result[0].page_number == 2
    assert result[0].text == "Hello world"
    assert result[0].char_count == 11
    assert result[0].ocr_used is True
    assert result[0].ocr_confidence == 90.0