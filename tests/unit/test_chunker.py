from ai_engine.chunking.chunker import chunk_pages
from document_processing.parsers.base import PageText


def page(number: int, text: str) -> PageText:
    return PageText(number, text, len(text))


def test_single_short_page():
    chunks = chunk_pages([page(1, "Contrat de compte.")])
    assert len(chunks) == 1
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 1)


def test_page_ranges_without_overlap():
    pages = [page(1, "a" * 100), page(2, "b" * 100), page(3, "c" * 100)]
    chunks = chunk_pages(pages, max_chars=250, overlap_chars=0)
    assert len(chunks) == 2
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 2)
    assert (chunks[1].page_start, chunks[1].page_end) == (3, 3)
    assert [c.index for c in chunks] == [0, 1]


def test_overlap_repeats_last_paragraph():
    pages = [page(1, "a" * 100), page(2, "b" * 100), page(3, "c" * 100)]
    chunks = chunk_pages(pages, max_chars=250, overlap_chars=150)
    assert len(chunks) == 2
    assert (chunks[1].page_start, chunks[1].page_end) == (2, 3)


def test_long_paragraph_is_split_and_respects_max():
    text = "Phrase numéro un. " * 200
    chunks = chunk_pages([page(1, text)], max_chars=500, overlap_chars=0)
    assert len(chunks) > 1
    assert all(len(c.text) <= 500 for c in chunks)
    assert sum(c.text.count("Phrase numéro un.") for c in chunks) == 200


def test_empty_pages_are_skipped():
    assert chunk_pages([page(1, ""), page(2, "   ")]) == []


def test_prompt_text_has_page_markers():
    chunks = chunk_pages([page(1, "Texte un."), page(2, "Texte deux.")])
    assert len(chunks) == 1
    assert "[Page 1]" in chunks[0].prompt_text
    assert "[Page 2]" in chunks[0].prompt_text
    assert "[Page" not in chunks[0].text