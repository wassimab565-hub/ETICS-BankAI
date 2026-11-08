import re

from ai_engine.chunking.chunker import Chunk

KEYWORDS = re.compile(
    r"\b(taeg|teg|taux)\b|int[ée]r[êe]ts?\b|\bfrais\b|tarif|commission|cotisation|"
    r"€|\beuros?\b|\bdur[ée]e\b|pr[ée]avis|r[ée]sili|p[ée]nalit|retard|rembours|"
    r"[ée]ch[ée]ance|mensualit|prend effet|entre en vigueur|date d.effet|"
    r"interest|\bfees?\b|notice period|terminat|\bpenalt",
    re.IGNORECASE,
)


def select_chunks(chunks: list[Chunk], always_first: int = 1) -> list[int]:
    """Indexes of the chunks worth sending to the model.

    The first chunks always go (title, bank, type and date are usually there); the
    others only if they contain a financial or contractual keyword.
    """
    return [
        chunk.index
        for position, chunk in enumerate(chunks)
        if position < always_first or KEYWORDS.search(chunk.text)
    ]