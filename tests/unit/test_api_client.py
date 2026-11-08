import json

import httpx
import pytest

from frontend.api_client import ApiClient, ApiError


def make_client(handler):
    return ApiClient("http://test", transport=httpx.MockTransport(handler))


def test_list_documents_sends_only_set_filters():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    assert make_client(handler).list_documents(status="needs_review", q="") == []
    assert seen == {"path": "/documents", "params": {"status": "needs_review"}}


def test_upload_sends_the_file():
    seen = {}

    def handler(request):
        seen["route"] = (request.method, request.url.path)
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.read()
        return httpx.Response(200, json={"duplicate": False, "document": {"id": 1}})

    result = make_client(handler).upload("a.pdf", b"%PDF-1.7 test")

    assert result["document"]["id"] == 1
    assert seen["route"] == ("POST", "/documents/upload")
    assert seen["content_type"].startswith("multipart/form-data")
    assert b'filename="a.pdf"' in seen["body"] and b"%PDF-1.7 test" in seen["body"]


def test_error_detail_is_exposed():
    client = make_client(
        lambda request: httpx.Response(409, json={"detail": "Analysis already in progress."})
    )
    with pytest.raises(ApiError) as info:
        client.start_analysis(1)
    assert info.value.status_code == 409
    assert "already in progress" in str(info.value)


def test_unreachable_api_gives_a_clear_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ApiError) as info:
        make_client(handler).stats()
    assert "indisponible" in str(info.value)
    assert info.value.status_code is None


def test_review_field_payload():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["json"] = json.loads(request.read())
        return httpx.Response(201, json={"id": 1})

    make_client(handler).review_field(31, "Wassim", "confirmed", corrected_value="2,50")

    assert seen["path"] == "/fields/31/review"
    assert seen["json"] == {
        "reviewer_name": "Wassim",
        "decision": "confirmed",
        "corrected_value": "2,50",
        "notes": None,
    }


def test_analysis_routes():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(202 if request.method == "POST" else 200, json={"ok": True})

    client = make_client(handler)
    client.start_analysis(7)
    client.status(7)
    client.results(7)

    assert calls == [
        ("POST", "/documents/7/analyze"),
        ("GET", "/documents/7/status"),
        ("GET", "/documents/7/results"),
    ]