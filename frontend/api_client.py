import os

import httpx

DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


class ApiError(Exception):
    """An API call failed. The message is meant to be shown to the user."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return "; ".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail)
    return f"Erreur {response.status_code}"


class ApiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError("API indisponible : vérifiez que le serveur est démarré.") from exc
        if response.is_error:
            raise ApiError(_detail(response), response.status_code)
        return response.json()

    # health
    def health(self) -> dict:
        return self._request("GET", "/health")

    def ollama(self) -> dict:
        return self._request("GET", "/health/ollama")

    def stats(self) -> dict:
        return self._request("GET", "/stats")

    # documents
    def list_documents(
        self,
        status: str | None = None,
        review_priority: str | None = None,
        document_type: str | None = None,
        q: str | None = None,
    ) -> list[dict]:
        params = {
            key: value
            for key, value in {
                "status": status,
                "review_priority": review_priority,
                "document_type": document_type,
                "q": q,
            }.items()
            if value
        }
        return self._request("GET", "/documents", params=params)

    def upload(self, filename: str, content: bytes) -> dict:
        files = {"file": (filename, content, "application/octet-stream")}
        return self._request("POST", "/documents/upload", files=files)

    # analysis
    def start_analysis(self, document_id: int) -> dict:
        return self._request("POST", f"/documents/{document_id}/analyze")

    def status(self, document_id: int) -> dict:
        return self._request("GET", f"/documents/{document_id}/status")

    def results(self, document_id: int) -> dict:
        return self._request("GET", f"/documents/{document_id}/results")

    # human review
    def review_field(
        self,
        field_id: int,
        reviewer_name: str,
        decision: str,
        corrected_value: str | None = None,
        notes: str | None = None,
    ) -> dict:
        body = {
            "reviewer_name": reviewer_name,
            "decision": decision,
            "corrected_value": corrected_value,
            "notes": notes,
        }
        return self._request("POST", f"/fields/{field_id}/review", json=body)

    def review_finding(
        self,
        finding_id: int,
        reviewer_name: str,
        decision: str,
        notes: str | None = None,
    ) -> dict:
        body = {"reviewer_name": reviewer_name, "decision": decision, "notes": notes}
        return self._request("POST", f"/findings/{finding_id}/review", json=body)