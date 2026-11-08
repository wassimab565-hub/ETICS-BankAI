import pymupdf

ROW_TOLERANCE = 3.0  # points: words whose centers are this close share a row


def group_words_into_rows(words: list[tuple], tolerance: float = ROW_TOLERANCE) -> list[str]:
    """Group words (PyMuPDF 'words' tuples) into text rows by vertical position."""
    ordered = sorted(words, key=lambda w: (w[1] + w[3]) / 2)
    rows: list[list[tuple]] = []
    anchor = None
    for word in ordered:
        y = (word[1] + word[3]) / 2
        if anchor is None or abs(y - anchor) > tolerance:
            rows.append([])
            anchor = y
        rows[-1].append(word)
    return [" ".join(w[4] for w in sorted(row, key=lambda w: w[0])) for row in rows]


def _inside(bbox: tuple, x: float, y: float) -> bool:
    x0, y0, x1, y1 = bbox
    return x0 <= x <= x1 and y0 <= y <= y1


def page_text_with_tables(page: pymupdf.Page) -> str:
    """Page text where each detected table is rebuilt row by row.

    Text outside tables keeps the original reading order. If table detection fails,
    the standard page text is returned.
    """
    try:
        tables = page.find_tables().tables
    except Exception:
        return page.get_text("text")
    if not tables:
        return page.get_text("text")

    words = page.get_text("words")
    emitted: set[int] = set()
    parts: list[str] = []
    for block in page.get_text("blocks", sort=True):
        if block[6] != 0:  # image block
            continue
        cx, cy = (block[0] + block[2]) / 2, (block[1] + block[3]) / 2
        index = next((i for i, t in enumerate(tables) if _inside(t.bbox, cx, cy)), None)
        if index is None:
            parts.append(block[4].strip())
        elif index not in emitted:
            emitted.add(index)
            bbox = tables[index].bbox
            table_words = [
                w for w in words
                if _inside(bbox, (w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
            ]
            parts.append("\n".join(group_words_into_rows(table_words)))
    return "\n\n".join(p for p in parts if p)