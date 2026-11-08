import re
from dataclasses import dataclass

from ai_engine.chunking.chunker import Chunk, Line

EXTRACTION_MAX_LINES = 5  # tables need the label line and the value line
RISK_MAX_LINES = 3
CONTEXT_LINES = 3  # how far we look for the start/end of a sentence
NON_VERBATIM_FIELDS = {"document_type"}  # classification, not copied from the text

_NUMBER = re.compile(r"\d[\d\s.,]*\d|\d")
_BOUNDARY = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÀ-ÖØ-Þ•])")

_WORD_NUMBERS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11,
    "douze": 12, "quinze": 15, "vingt": 20, "trente": 30, "soixante": 60,
    "quatre-vingt-dix": 90,
}
_UNITS = r"(?:jours?|mois|semaines?|ans?|années?|heures?)"
_WORD_NUMBER = re.compile(
    r"\b("
    + "|".join(sorted(map(re.escape, _WORD_NUMBERS), key=len, reverse=True))
    + rf")\s+{_UNITS}\b",
    re.IGNORECASE,
)


class EvidenceError(Exception):
    """The line numbers given by the model cannot be used."""


@dataclass
class Evidence:
    text: str
    page_start: int
    page_end: int
    line_start: int
    line_end: int


def _expand_to_sentences(lines: list[Line], first: int, last: int) -> tuple[str, int, int]:
    """Extend the selected lines (indexes) to the sentences they touch.

    Looks at most CONTEXT_LINES lines around. If no sentence boundary is found on one
    side (tables, lists), that side is left unchanged.
    """
    ctx_first = max(0, first - CONTEXT_LINES)
    ctx_last = min(len(lines) - 1, last + CONTEXT_LINES)
    window = lines[ctx_first : ctx_last + 1]

    offsets: list[int] = []
    pos = 0
    for line in window:
        offsets.append(pos)
        pos += len(line.text) + 1
    context = " ".join(line.text for line in window)

    sel_start = offsets[first - ctx_first]
    sel_end = offsets[last - ctx_first] + len(lines[last].text)

    boundaries = list(_BOUNDARY.finditer(context))
    left = max((m.end() for m in boundaries if m.end() <= sel_start), default=sel_start)
    right = min((m.start() for m in boundaries if m.start() >= sel_end), default=sel_end)

    touched = [
        ctx_first + i
        for i, line in enumerate(window)
        if offsets[i] < right and offsets[i] + len(line.text) > left
    ]
    return context[left:right].strip(), touched[0], touched[-1]


def resolve_evidence(
    chunk: Chunk, line_numbers: list[int], max_lines: int = EXTRACTION_MAX_LINES
) -> Evidence:
    """Rebuild the verbatim quote (extended to full sentences) from the model's line numbers."""
    if not line_numbers:
        raise EvidenceError("no line numbers")

    lines = chunk.lines
    index_of = {line.number: i for i, line in enumerate(lines)}
    unknown = sorted(n for n in set(line_numbers) if n not in index_of)
    if unknown:
        raise EvidenceError(f"unknown line numbers: {unknown}")

    start, end = min(line_numbers), max(line_numbers)
    if end - start + 1 > max_lines:
        raise EvidenceError(f"evidence spans {end - start + 1} lines (max {max_lines})")

    text, first, last = _expand_to_sentences(lines, index_of[start], index_of[end])
    return Evidence(
        text=text,
        page_start=lines[first].page,
        page_end=lines[last].page,
        line_start=lines[first].number,
        line_end=lines[last].number,
    )


def numbers_in(text: str) -> list[float]:
    """All numbers in a text: '1 000,50' -> 1000.5, and 'huit jours' -> 8."""
    found: list[float] = []
    for match in _NUMBER.findall(text):
        cleaned = re.sub(r"\s", "", match).replace(",", ".")
        candidates = {cleaned}
        if "." in cleaned:
            candidates.add(cleaned.replace(".", ""))  # '1.000' may mean one thousand
        for candidate in candidates:
            try:
                found.append(float(candidate))
            except ValueError:
                continue
    for word in _WORD_NUMBER.findall(text):  # only when followed by a time unit
        found.append(float(_WORD_NUMBERS[word.lower()]))
    return found


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def value_in_evidence(value: str | int | float, evidence: str) -> bool:
    """Check that the extracted value really appears in the quoted text."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return any(abs(n - float(value)) < 1e-9 for n in numbers_in(evidence))

    if _norm(str(value)) in _norm(evidence):
        return True
    wanted = numbers_in(str(value))
    available = numbers_in(evidence)
    return bool(wanted) and all(
        any(abs(w - a) < 1e-9 for a in available) for w in wanted
    )

def text_in_chunk(text: str, chunk: Chunk) -> bool:
    """Check that a label really appears in the chunk (labels must not be invented)."""
    return _norm(text) in _norm(chunk.text)