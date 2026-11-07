import sys
from pathlib import Path

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.llm.json_client import chat_json
from ai_engine.prompts.extraction import EXTRACTION_SYSTEM, build_extraction_prompt
from ai_engine.prompts.risk_analysis import RISK_SYSTEM, build_risk_prompt
from ai_engine.validation.evidence import EvidenceError, resolve_evidence, value_in_evidence
from ai_engine.validation.llm_schemas import ExtractionOutput, RiskOutput
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages

filename, index = sys.argv[1], int(sys.argv[2])
chunks = chunk_pages(clean_pages(parse_pdf(Path("data/raw") / filename)))
chunk = chunks[index]
print(f"chunk {index}/{len(chunks) - 1} | pages {chunk.page_start}-{chunk.page_end} | {len(chunk.lines)} lines\n")

numbered = chunk.numbered_text
tasks = [
    ("EXTRACTION", EXTRACTION_SYSTEM, build_extraction_prompt(numbered), ExtractionOutput, "fields"),
    ("RISK", RISK_SYSTEM, build_risk_prompt(numbered), RiskOutput, "findings"),
]
for name, system, prompt, model, key in tasks:
    parsed, meta = chat_json(prompt, model, system=system)
    items = getattr(parsed, key)
    print(f"=== {name}: {len(items)} items | {meta}")
    for item in items:
        data = item.model_dump()
        try:
            ev = resolve_evidence(chunk, item.evidence_lines)
        except EvidenceError as exc:
            print(f"  BAD LINES ({exc}): {data}")
            continue
        status = ""
        if key == "fields":
            status = "value OK" if value_in_evidence(item.value, ev.text) else "VALUE NOT IN EVIDENCE"
        data["evidence"] = ev.text[:200]
        data["page"] = ev.page_start
        print(f"  {status}  {data}")
    print()