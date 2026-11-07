import json
import re

from pydantic import BaseModel, ValidationError

from ai_engine.llm.ollama_client import chat

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LLMOutputError(Exception):
    """The model did not return valid structured output after all retries."""


def parse_json(text: str) -> dict:
    """Parse a JSON object from model output (tolerates code fences and extra text)."""
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _short_error(exc: Exception) -> str:
    """Short error description that never repeats document content."""
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]
        )
    return f"invalid JSON ({type(exc).__name__})"


def chat_json(
    prompt: str,
    model_cls: type[BaseModel],
    system: str | None = None,
    max_retries: int = 2,
    **chat_kwargs,
) -> tuple[BaseModel, dict]:
    """Ask the model for JSON matching model_cls. Retries on invalid output.

    Returns (validated object, meta). Raises LLMOutputError if every attempt fails.
    """
    schema = model_cls.model_json_schema()
    attempt_prompt = prompt
    total_s, total_tokens, last_error = 0.0, 0, "unknown"

    for attempt in range(1, max_retries + 2):
        result = chat(attempt_prompt, system=system, json_format=schema, **chat_kwargs)
        total_s += result["duration_s"]
        total_tokens += result.get("output_tokens") or 0
        try:
            parsed = model_cls.model_validate(parse_json(result["content"]))
        except ValueError as exc:  # JSONDecodeError and ValidationError are ValueErrors
            last_error = _short_error(exc)
            attempt_prompt = (
                f"{prompt}\n\nYour previous answer was invalid: {last_error}. "
                "Return only valid JSON that matches the requested structure."
            )
            continue
        meta = {
            "attempts": attempt,
            "duration_s": round(total_s, 1),
            "output_tokens": total_tokens,
        }
        return parsed, meta

    raise LLMOutputError(f"Invalid model output after {max_retries + 1} attempts: {last_error}")