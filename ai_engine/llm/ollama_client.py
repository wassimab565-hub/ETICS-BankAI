import re
import time

import httpx

from backend.core.config import settings

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaError(Exception):
    pass


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks if the model emits them anyway."""
    return _THINK_BLOCK.sub("", text).strip()


def check_ollama(timeout: float = 5.0) -> dict:
    """Check that Ollama is running and that the configured model is installed."""
    url = f"{settings.ollama_base_url}/api/tags"
    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return {"ollama": "unreachable", "model": settings.ollama_model, "error": str(exc)}

    installed = [m["name"] for m in response.json().get("models", [])]
    return {
        "ollama": "up",
        "model": settings.ollama_model,
        "model_available": settings.ollama_model in installed,
    }


def chat(
    prompt: str,
    system: str | None = None,
    json_format: dict | str | None = None,
    temperature: float = 0.0,
    num_ctx: int | None = None,
    timeout: float | None = None,
) -> dict:
    """Send one prompt to Qwen3 through Ollama. Returns content and basic timing."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx or settings.ollama_num_ctx,
        },
    }
    if json_format is not None:
        payload["format"] = json_format

    start = time.time()
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            timeout=timeout or settings.ollama_timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaError(f"Ollama request failed: {type(exc).__name__}") from exc

    data = response.json()
    return {
        "content": strip_think(data["message"]["content"]),
        "duration_s": round(time.time() - start, 1),
        "output_tokens": data.get("eval_count"),
    }