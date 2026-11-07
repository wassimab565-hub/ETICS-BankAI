import httpx

from backend.core.config import settings


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