import io

import pymupdf
import pytesseract
from PIL import Image

OCR_LANGS = "fra+eng"
OCR_DPI = 300


def ocr_page(
    page: pymupdf.Page, lang: str = OCR_LANGS, dpi: int = OCR_DPI
) -> tuple[str, float | None]:
    """Render a PDF page to an image and run Tesseract. Returns (text, avg confidence)."""
    pix = page.get_pixmap(dpi=dpi)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    data = pytesseract.image_to_data(
        image, lang=lang, output_type=pytesseract.Output.DICT
    )

    lines: dict[tuple, list[str]] = {}
    confidences: list[float] = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
        conf = float(data["conf"][i])
        if conf >= 0:
            confidences.append(conf)

    text = "\n".join(" ".join(words) for words in lines.values())
    confidence = round(sum(confidences) / len(confidences), 1) if confidences else None
    return text, confidence