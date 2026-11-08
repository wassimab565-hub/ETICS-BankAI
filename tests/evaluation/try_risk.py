import sys
from pathlib import Path

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.toxicity.service import analyze_chunk, analyze_document
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages

filename = sys.argv[1]
chunks = chunk_pages(clean_pages(parse_pdf(Path("data/raw") / filename)))

dropped: list[dict] = []
if len(sys.argv) > 2:
    findings, dropped = analyze_chunk(chunks[int(sys.argv[2])])
else:
    result = analyze_document(
        chunks, on_progress=lambda done, total: print(f"chunk {done}/{total} done", flush=True)
    )
    findings = result.findings
    print(
        f"\nanalyzed {result.chunks_analyzed}/{result.chunks_total} | "
        f"failed {result.failed_chunks} | complete={result.is_complete}"
    )

print(f"\n{len(findings)} finding(s)  (I=impact, U=unclear, B=bank decides alone)\n")
for f in findings:
    c = f.criteria
    flags = "".join(
        letter if value else "-"
        for letter, value in (
            ("I", c.impacts_customer),
            ("U", c.unclear_for_customer),
            ("B", c.bank_decides_alone),
        )
    )
    print(f"[{flags}] {f.category:<22} p{f.source.page_start}  {f.source.evidence[:220]}")
    print(f"      -> {f.explanation}\n")
if dropped:
    print("dropped:", dropped)