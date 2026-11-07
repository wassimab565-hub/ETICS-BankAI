import re
import unicodedata
from dataclasses import replace

from document_processing.parsers.base import PageText

LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}
SPACES = {"\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u2007": " ", "\t": " "}
INVISIBLE = {"\u00ad", "\u200b", "\u200c", "\u200d", "\ufeff"}

_LOWER = "a-zàâäçéèêëîïôöûùüÿœæ"
# word split by a line-break hyphen: "conven-\ntion" -> "convention"
_HYPHEN_BREAK = re.compile(rf"(?<=[{_LOWER}])-\n(?=[{_LOWER}])")
_MULTI_SPACES = re.compile(r" {2,}")
_MULTI_NEWLINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalize extracted text without changing its meaning."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    for src, dst in {**LIGATURES, **SPACES}.items():
        text = text.replace(src, dst)

    text = "".join(
        ch
        for ch in text
        if ch not in INVISIBLE and (ch == "\n" or unicodedata.category(ch) != "Cc")
    )

    lines = [_MULTI_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)

    text = _HYPHEN_BREAK.sub("", text)
    text = _MULTI_NEWLINES.sub("\n\n", text)
    return text.strip()


def clean_pages(pages: list[PageText]) -> list[PageText]:
    """Clean every page, keeping page numbers and OCR information."""
    cleaned = []
    for page in pages:
        text = clean_text(page.text)
        cleaned.append(replace(page, text=text, char_count=len(text)))
    return cleaned