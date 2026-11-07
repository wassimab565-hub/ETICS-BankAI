import pytest

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.validation.evidence import (
    EvidenceError,
    resolve_evidence,
    value_in_evidence,
)
from document_processing.parsers.base import PageText


def make_chunk():
    page1 = "Tenue de compte\nActif\nPar mois\n2,40 €\n\nAutre ligne"
    pages = [PageText(1, page1, len(page1)), PageText(2, "Page deux", 9)]
    return chunk_pages(pages)[0]


def test_numbered_text_has_line_and_page_markers():
    text = make_chunk().numbered_text
    assert "[L1] Tenue de compte" in text
    assert "[Page 2]\n[L6] Page deux" in text


def test_resolve_evidence_rebuilds_verbatim_quote():
    ev = resolve_evidence(make_chunk(), [1, 4])
    assert ev.text == "Tenue de compte Actif Par mois 2,40 €"
    assert (ev.page_start, ev.page_end) == (1, 1)
    assert (ev.line_start, ev.line_end) == (1, 4)


def test_resolve_evidence_unknown_line():
    with pytest.raises(EvidenceError):
        resolve_evidence(make_chunk(), [99])


def test_resolve_evidence_too_many_lines():
    with pytest.raises(EvidenceError):
        resolve_evidence(make_chunk(), [1, 4], max_lines=2)


def test_resolve_evidence_spans_pages():
    ev = resolve_evidence(make_chunk(), [5, 6])
    assert (ev.page_start, ev.page_end) == (1, 2)


def test_value_number_formats():
    assert value_in_evidence(2.4, "Tenue de compte 2,40 €")
    assert not value_in_evidence(2.5, "Tenue de compte 2,40 €")
    assert value_in_evidence(1000.5, "Plafond : 1 000,50 €")


def test_value_string():
    assert value_in_evidence("Banque X", "Contrat avec la Banque X")
    assert not value_in_evidence("Banque Y", "Contrat avec la Banque X")