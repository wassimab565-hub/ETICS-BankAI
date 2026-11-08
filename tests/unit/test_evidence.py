import pytest

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.validation.evidence import (
    EvidenceError,
    duration_in,
    resolve_evidence,
    text_in_chunk,
    value_in_evidence,
)
from document_processing.parsers.base import PageText


def make_chunk():
    page1 = "Tenue de compte\nActif\nPar mois\n2,40 €\n\nAutre ligne"
    pages = [PageText(1, page1, len(page1)), PageText(2, "Page deux", 9)]
    return chunk_pages(pages)[0]


def sentence_chunk():
    text = (
        "Vous pouvez résilier l’Offre, à tout moment, par écrit, moyennant\n"
        "un préavis de huit jours. Nous pouvons résilier avec un préavis de deux mois, dès\n"
        "lors que vous ne répondez plus aux critères. L’Offre prend fin."
    )
    return chunk_pages([PageText(1, text, len(text))])[0]


def test_numbered_text_has_line_and_page_markers():
    text = make_chunk().numbered_text
    assert "[L1] Tenue de compte" in text
    assert "[Page 2]\n[L6] Page deux" in text


def test_resolve_evidence_table_is_not_expanded():
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


def test_evidence_expands_to_end_of_sentence():
    ev = resolve_evidence(sentence_chunk(), [1])
    assert ev.text == (
        "Vous pouvez résilier l’Offre, à tout moment, par écrit, moyennant "
        "un préavis de huit jours."
    )
    assert (ev.line_start, ev.line_end) == (1, 2)


def test_evidence_expands_to_start_and_end_of_sentence():
    ev = resolve_evidence(sentence_chunk(), [3])
    assert ev.text.startswith("Nous pouvons résilier")
    assert ev.text.endswith("L’Offre prend fin.")
    assert ev.line_start == 2


def test_value_number_formats():
    assert value_in_evidence(2.4, "Tenue de compte 2,40 €")
    assert not value_in_evidence(2.5, "Tenue de compte 2,40 €")
    assert value_in_evidence(1000.5, "Plafond : 1 000,50 €")


def test_value_string():
    assert value_in_evidence("Banque X", "Contrat avec la Banque X")
    assert not value_in_evidence("Banque Y", "Contrat avec la Banque X")


def test_value_number_words_need_a_unit():
    assert value_in_evidence("8", "moyennant un préavis de huit jours")
    assert value_in_evidence(2, "avec un préavis de deux mois")
    assert not value_in_evidence(1, "un contrat de compte")

def test_text_in_chunk_ignores_line_breaks_and_case():
    chunk = make_chunk()
    assert text_in_chunk("tenue de compte actif", chunk)
    assert not text_in_chunk("Carte Visa Gold", chunk)

def test_duration_in():
    assert duration_in("un préavis de huit jours") == (8.0, "days")
    assert duration_in("avec 2 mois de délai") == (2.0, "months")
    assert duration_in("pour un an") == (1.0, "years")
    assert duration_in("aucune durée ici") is None