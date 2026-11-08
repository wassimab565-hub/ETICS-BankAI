import sys
from pathlib import Path

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.extraction.service import extract_document
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages

filename = sys.argv[1]
chunks = chunk_pages(clean_pages(parse_pdf(Path("data/raw") / filename)))
result = extract_document(
    chunks, on_progress=lambda done, total: print(f"chunk {done}/{total} done", flush=True)
)

counts: dict[str, int] = {}
for field in result.fields:
    counts[field.status.value] = counts.get(field.status.value, 0) + 1
print(
    f"\nanalyzed {result.chunks_analyzed}/{result.chunks_total} | "
    f"failed {result.failed_chunks} | complete={result.is_complete}"
)
print(counts, "\n")
for f in result.fields:
    value = f.value_number if f.value_number is not None else f.raw_value[:30]
    print(
        f"{f.status.value:<13} {f.field_name:<26} {str(value):<30} "
        f"{f.unit or '':<10} p{f.source.page_start} {f.label or ''} {f.issues}"
    )
print("\nmissing:", result.missing_fields())