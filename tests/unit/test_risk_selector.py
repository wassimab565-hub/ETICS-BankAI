from ai_engine.chunking.chunker import chunk_pages
from ai_engine.toxicity.chunk_selector import risk_signals, select_risk_chunks
from document_processing.parsers.base import PageText


def chunks_from(*texts):
    pages = [PageText(i + 1, t, len(t)) for i, t in enumerate(texts)]
    return chunk_pages(pages, max_chars=80, overlap_chars=0)


CLAUSE = "Nous pouvons résilier l’Offre avec un préavis de deux mois."
NEUTRAL = "Présentation générale du document et de ses annexes."
ONE_SIGNAL = "La banque décline toute responsabilité en pareil cas."


def test_selects_clause_chunk():
    assert risk_signals(CLAUSE) == {"termination", "notice"}
    assert select_risk_chunks(chunks_from(CLAUSE)) == [0]


def test_skips_neutral_and_single_signal_chunks():
    chunks = chunks_from(NEUTRAL, ONE_SIGNAL)
    assert len(chunks) == 2
    assert select_risk_chunks(chunks) == []


def test_min_signals_can_be_lowered():
    chunks = chunks_from(NEUTRAL, ONE_SIGNAL)
    assert select_risk_chunks(chunks, min_signals=1) == [1]