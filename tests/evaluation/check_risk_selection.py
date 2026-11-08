from pathlib import Path

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.toxicity.chunk_selector import select_risk_chunks
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages

print(f"{'file':<62}{'chunks':>7}{'sent':>6}{'%':>5}")
total, sent = 0, 0
for pdf in sorted(Path("data/raw").glob("*.pdf")):
    chunks = chunk_pages(clean_pages(parse_pdf(pdf)))
    chosen = select_risk_chunks(chunks)
    total += len(chunks)
    sent += len(chosen)
    print(f"{pdf.name[:60]:<62}{len(chunks):>7}{len(chosen):>6}{round(100 * len(chosen) / max(len(chunks), 1)):>5}")
print(f"\nTOTAL: {sent} chunks sent out of {total}")