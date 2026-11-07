import time
from pathlib import Path

from ai_engine.chunking.chunker import chunk_pages
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages

RAW_DIR = Path("data/raw")

print(f"{'file':<62}{'pages':>6}{'chars':>9}{'ocr':>5}{'chunks':>8}{'sec':>6}")
for pdf in sorted(RAW_DIR.glob("*.pdf")):
    start = time.time()
    try:
        pages = clean_pages(parse_pdf(pdf))
        chunks = chunk_pages(pages)
        chars = sum(p.char_count for p in pages)
        ocr_pages = sum(p.ocr_used for p in pages)
        print(
            f"{pdf.name[:60]:<62}{len(pages):>6}{chars:>9}{ocr_pages:>5}"
            f"{len(chunks):>8}{time.time() - start:>6.1f}"
        )
    except Exception as exc:
        print(f"{pdf.name[:60]:<62} ERROR: {type(exc).__name__}: {exc}")