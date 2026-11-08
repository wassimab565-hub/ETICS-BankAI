import logging
from collections.abc import Callable

from ai_engine.chunking.chunker import Chunk
from ai_engine.extraction.schemas import FieldSource
from ai_engine.llm.json_client import LLMOutputError, chat_json
from ai_engine.llm.ollama_client import OllamaError
from ai_engine.prompts.risk_analysis import (
    RISK_PROMPT_VERSION,
    RISK_SYSTEM,
    build_risk_prompt,
)
from ai_engine.toxicity.chunk_selector import select_risk_chunks
from ai_engine.toxicity.schemas import RiskCriteria, RiskFinding, RiskResult
from ai_engine.validation.evidence import RISK_MAX_LINES, EvidenceError, resolve_evidence
from ai_engine.validation.llm_schemas import RiskOutput
from backend.core.config import settings

logger = logging.getLogger(__name__)


def analyze_chunk(chunk: Chunk) -> tuple[list[RiskFinding], list[dict]]:
    """Run the risk analysis on one chunk. Returns (findings, dropped items with the reason).

    A finding whose line numbers cannot be used is dropped: without a verbatim
    evidence, it cannot be kept. The severity is computed later (phase 6.3).
    """
    prompt = build_risk_prompt(chunk.numbered_text)
    parsed, _meta = chat_json(prompt, RiskOutput, system=RISK_SYSTEM)

    findings: list[RiskFinding] = []
    dropped: list[dict] = []
    for raw in parsed.findings:
        try:
            ev = resolve_evidence(chunk, raw.evidence_lines, max_lines=RISK_MAX_LINES)
        except EvidenceError as exc:
            dropped.append({"category": raw.category, "reason": str(exc)})
            continue
        findings.append(
            RiskFinding(
                category=raw.category,
                explanation=raw.explanation.strip(),
                suggested_action=raw.suggested_action.strip(),
                criteria=RiskCriteria(
                    impacts_customer=raw.impacts_customer,
                    unclear_for_customer=raw.unclear_for_customer,
                    bank_decides_alone=raw.bank_decides_alone,
                ),
                source=FieldSource(
                    chunk_index=chunk.index,
                    page_start=ev.page_start,
                    page_end=ev.page_end,
                    line_start=ev.line_start,
                    line_end=ev.line_end,
                    evidence=ev.text,
                ),
            )
        )
    return findings, dropped


def analyze_document(
    chunks: list[Chunk],
    select: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
) -> RiskResult:
    """Risk analysis of a whole document.

    chunks_total counts the chunks sent to the model (after selection). A failing
    chunk is recorded in failed_chunks and the others are still processed.
    """
    by_index = {chunk.index: chunk for chunk in chunks}
    indexes = select_risk_chunks(chunks) if select else list(by_index)

    result = RiskResult(
        model_name=settings.ollama_model,
        prompt_version=RISK_PROMPT_VERSION,
        chunks_total=len(indexes),
    )
    for position, index in enumerate(indexes, start=1):
        try:
            findings, dropped = analyze_chunk(by_index[index])
        except (LLMOutputError, OllamaError) as exc:
            logger.warning("risk chunk %s failed: %s", index, type(exc).__name__)
            result.failed_chunks.append(index)
        else:
            result.findings.extend(findings)
            result.chunks_analyzed += 1
            if dropped:
                logger.info("risk chunk %s: %s item(s) dropped", index, len(dropped))
        if on_progress:
            on_progress(position, len(indexes))
    return result