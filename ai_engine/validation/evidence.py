import re
from dataclasses import dataclass

from ai_engine.chunking.chunker import Chunk

MAX_EVIDENCE_LINES = 8
_NUMBER = re.compile(r"\d[\d\s.,]*\d|\d")


class EvidenceError(Exception):
    """The line numbers given by the model cannot be used."""


@dataclass
class Evidence:
    text: str
    page_start: int
    page_end: int
    line_start: int
    line_end: int


def resolve_evidence(
    chunk: Chunk, line_numbers: list[int], max_lines: int = MAX_EVIDENCE_LINES
) -> Evidence:
    """Rebuild the verbatim quote and its pages from the line numbers of the model."""
    if not line_numbers:
        raise EvidenceError("no line numbers")

    by_number = {line.number: line for line in chunk.lines}
    unknown = sorted(n for n in set(line_numbers) if n not in by_number)
    if unknown:
        raise EvidenceError(f"unknown line numbers: {unknown}")

    start, end = min(line_numbers), max(line_numbers)
    if end - start + 1 > max_lines:
        raise EvidenceError(f"evidence spans {end - start + 1} lines (max {max_lines})")

    selected = [by_number[n] for n in range(start, end + 1)]
    return Evidence(
        text=" ".join(line.text for line in selected),
        page_start=selected[0].page,
        page_end=selected[-1].page,
        line_start=start,
        line_end=end,
    )


def numbers_in(text: str) -> list[float]:
    """All numbers in a text, understanding French formats ('1 000,50' -> 1000.5)."""
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
    return found


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def value_in_evidence(value: str | int | float, evidence: str) -> bool:
    """Check that the extracted value really appears in the quoted lines."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return any(abs(n - float(value)) < 1e-9 for n in numbers_in(evidence))

    if _norm(str(value)) in _norm(evidence):
        return True
    wanted = numbers_in(str(value))
    available = numbers_in(evidence)
    return bool(wanted) and all(
        any(abs(w - a) < 1e-9 for a in available) for w in wanted
    )