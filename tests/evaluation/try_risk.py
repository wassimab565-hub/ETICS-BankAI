import sys
from pathlib import Path

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.toxicity.rules import post_process, review_priority
from ai_engine.toxicity.schemas import RiskResult
from ai_engine.toxicity.service import analyze_chunk, analyze_document
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages

filename = sys.argv[1]
chunks = chunk_pages(clean_pages(parse_pdf(Path("data/raw") / filename)))

dropped: list[dict] = []
if len(sys.argv) > 2:
    findings, dropped = analyze_chunk(chunks[int(sys.argv[2])])
    result = post_process(
        RiskResult(
            model_name="qwen3:8b",
            prompt_version="try",
            chunks_total=1,
            chunks_analyzed=1,
            findings=findings,
        )
    )
else:
    result = analyze_document(
        chunks, on_progress=lambda done, total: print(f"chunk {done}/{total} done", flush=True)
    )
    print(
        f"\nanalyzed {result.chunks_analyzed}/{result.chunks_total} | "
        f"failed {result.failed_chunks} | complete={result.is_complete}"
    )


def flags(c):
    return "".join(
        letter if value else "-"
        for letter, value in (
            ("I", c.impacts_customer),
            ("U", c.unclear_for_customer),
            ("B", c.bank_decides_alone),
        )
    )


priority = review_priority(result)
print(f"\nreview priority: {priority.value if priority else 'not assessed'} | {len(result.findings)} finding(s)")
print("(I=impact, U=unclear, B=bank decides alone: model -> after code)\n")
for f in result.findings:
    print(
        f"{f.severity.value.upper():<6} [{flags(f.model_criteria)}->{flags(f.criteria)}] "
        f"{f.category:<22} p{f.source.page_start}  {f.source.evidence[:220]}"
    )
    print(f"      -> {f.explanation}")
    for issue in f.issues:
        print(f"      !  {issue}")
    print()
if dropped:
    print("dropped:", dropped)