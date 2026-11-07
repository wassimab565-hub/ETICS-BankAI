import re
from dataclasses import dataclass

from document_processing.parsers.base import PageText

MAX_CHARS = 4000
OVERLAP_CHARS = 400
_SENTENCE_SPLIT = re.compile(r"(?<=[.;:!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")

Segment = tuple[int, str]  # (page_number, text)


@dataclass
class Chunk:
    index: int
    page_start: int
    page_end: int
    segments: list[Segment]

    @property
    def text(self) -> str:
        """Plain text: the reference used to verify evidence later."""
        return "\n\n".join(text for _, text in self.segments)

    @property
    def prompt_text(self) -> str:
        """Same text with [Page N] markers, to send to the LLM."""
        parts: list[str] = []
        current_page = None
        for page, text in self.segments:
            if page != current_page:
                parts.append(f"[Page {page}]")
                current_page = page
            parts.append(text)
        return "\n\n".join(parts)


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split an oversized paragraph on sentences, then on spaces if needed."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT.split(text):
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _segments(pages: list[PageText], max_chars: int) -> list[Segment]:
    segments: list[Segment] = []
    for page in pages:
        for paragraph in _PARAGRAPH_SPLIT.split(page.text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            for piece in _split_long(paragraph, max_chars):
                if piece:
                    segments.append((page.page_number, piece))
    return segments


def _overlap_tail(segments: list[Segment], overlap_chars: int) -> list[Segment]:
    tail: list[Segment] = []
    total = 0
    for seg in reversed(segments):
        total += len(seg[1]) + 2
        if total > overlap_chars:
            break
        tail.insert(0, seg)
    return tail


def _make_chunk(index: int, segments: list[Segment]) -> Chunk:
    pages = [page for page, _ in segments]
    return Chunk(
        index=index,
        page_start=min(pages),
        page_end=max(pages),
        segments=list(segments),
    )


def chunk_pages(
    pages: list[PageText],
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[Chunk]:
    """Group paragraphs into chunks, keeping page references and a small overlap."""
    chunks: list[Chunk] = []
    current: list[Segment] = []
    size = 0

    for seg in _segments(pages, max_chars):
        seg_len = len(seg[1]) + 2
        if current and size + seg_len > max_chars:
            chunks.append(_make_chunk(len(chunks), current))
            current = _overlap_tail(current, overlap_chars)
            size = sum(len(text) + 2 for _, text in current)
            if size + seg_len > max_chars:
                current, size = [], 0
        current.append(seg)
        size += seg_len

    if current:
        chunks.append(_make_chunk(len(chunks), current))
    return chunks