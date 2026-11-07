import sys
from pathlib import Path

from ai_engine.chunking.chunker import chunk_pages
from ai_engine.llm.json_client import chat_json
from ai_engine.prompts.extraction import EXTRACTION_SYSTEM, build_extraction_prompt
from ai_engine.prompts.risk_analysis import RISK_SYSTEM, build_risk_prompt
from ai_engine.validation.llm_schemas import ExtractionOutput, RiskOutput
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages


def norm(text: str) -> str:
    return " ".join(text.split())


filename, index = sys.argv[1], int(sys.argv[2])
chunks = chunk_pages(clean_pages(parse_pdf(Path("data/raw") / filename)))
chunk = chunks[index]
reference = norm(chunk.text)
print(f"chunk {index}/{len(chunks) - 1} | pages {chunk.page_start}-{chunk.page_end} | {len(chunk.text)} chars\n")

tasks = [
    ("EXTRACTION", EXTRACTION_SYSTEM, build_extraction_prompt(chunk.prompt_text), ExtractionOutput, "fields"),
    ("RISK", RISK_SYSTEM, build_risk_prompt(chunk.prompt_text), RiskOutput, "findings"),
]
for name, system, prompt, model, key in tasks:
    parsed, meta = chat_json(prompt, model, system=system)
    items = getattr(parsed, key)
    print(f"=== {name}: {len(items)} items | {meta}")
    for item in items:
        found = norm(item.evidence) in reference
        data = item.model_dump()
        data["evidence"] = data["evidence"][:90]
        print(("  evidence OK  " if found else "  evidence NOT FOUND  "), data)
    print()