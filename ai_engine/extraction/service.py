import logging
from collections.abc import Callable

from ai_engine.chunking.chunker import Chunk
from ai_engine.extraction.chunk_selector import select_chunks
from ai_engine.extraction.schemas import (
    ExtractedField,
    ExtractionResult,
    FieldSource,
    ValidationStatus,
)
from ai_engine.llm.json_client import LLMOutputError, chat_json
from ai_engine.llm.ollama_client import OllamaError
from ai_engine.prompts.extraction import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SYSTEM,
    build_extraction_prompt,
)
from ai_engine.validation.evidence import (
    EXTRACTION_MAX_LINES,
    EvidenceError,
    resolve_evidence,
)
from ai_engine.validation.llm_schemas import ExtractionOutput
from ai_engine.extraction.rules import post_process
from backend.core.config import settings

logger = logging.getLogger(__name__)


def extract_from_chunk(chunk: Chunk) -> tuple[list[ExtractedField], list[dict]]:
    """Run the model on one chunk. Returns (fields, dropped items with the reason).

    An item whose line numbers cannot be used is dropped: without a verbatim
    evidence, it cannot be kept. Values are validated later (phase 5.4).
    """
    prompt = build_extraction_prompt(chunk.numbered_text)
    parsed, _meta = chat_json(prompt, ExtractionOutput, system=EXTRACTION_SYSTEM)

    fields: list[ExtractedField] = []
    dropped: list[dict] = []
    for raw in parsed.fields:
        try:
            ev = resolve_evidence(chunk, raw.evidence_lines, max_lines=EXTRACTION_MAX_LINES)
        except EvidenceError as exc:
            dropped.append({"field_name": raw.field_name, "reason": str(exc)})
            continue
        fields.append(
            ExtractedField(
                field_name=raw.field_name,
                label=(raw.label or "").strip() or None,
                raw_value=str(raw.value),
                unit=raw.unit,
                source=FieldSource(
                    chunk_index=chunk.index,
                    page_start=ev.page_start,
                    page_end=ev.page_end,
                    line_start=ev.line_start,
                    line_end=ev.line_end,
                    evidence=ev.text,
                ),
                status=ValidationStatus.needs_review,
            )
        )
    return fields, dropped


def extract_document(
    chunks: list[Chunk],
    select: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
) -> ExtractionResult:
    """Extract fields from a whole document.

    chunks_total counts the chunks sent to the model (after selection). A failing
    chunk is recorded in failed_chunks and the others are still processed.
    """
    by_index = {chunk.index: chunk for chunk in chunks}
    indexes = select_chunks(chunks) if select else list(by_index)

    result = ExtractionResult(
        model_name=settings.ollama_model,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        chunks_total=len(indexes),
    )
    for position, index in enumerate(indexes, start=1):
        try:
            fields, dropped = extract_from_chunk(by_index[index])
        except (LLMOutputError, OllamaError) as exc:
            logger.warning("chunk %s failed: %s", index, type(exc).__name__)
            result.failed_chunks.append(index)
        else:
            result.fields.extend(fields)
            result.chunks_analyzed += 1
            if dropped:
                logger.info("chunk %s: %s item(s) dropped", index, len(dropped))
        if on_progress:
            on_progress(position, len(indexes))
    return post_process(result)