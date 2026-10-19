"""Synthetic responses: verify safety and schema checks, not actual model access."""
import asyncio
import importlib.util
import json
from pathlib import Path

import httpx

spec = importlib.util.spec_from_file_location("qwen_access", Path(__file__).parents[1] / "scripts/verify_qwen_access.py")
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)


def run(handler, **changes):
    config = {"key": "test-secret", "model": probe_module.MODEL, "base_url": probe_module.BASE_URL}
    config.update(changes)
    return asyncio.run(probe_module.probe(config, httpx.MockTransport(handler)))


def test_missing_key_or_unapproved_destination_never_sends():
    def forbidden(request):
        raise AssertionError("No request allowed")
    assert run(forbidden, key="")["status"] == "not_configured"
    assert run(forbidden, key="sk-sp-test")["status"] == "invalid_configuration"
    assert run(forbidden, base_url="https://example.com")["calls"] == 0
    assert run(forbidden, model="another-model")["calls"] == 0


def test_success_is_one_small_structured_request_without_document():
    calls = []
    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.url == probe_module.BASE_URL + "/chat/completions"
        assert payload["max_tokens"] == 128 and payload["enable_thinking"] is False
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert all(isinstance(item["content"], str) for item in payload["messages"])
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(probe_module.EXPECTED)}}], "usage": {
            "prompt_tokens": 35, "completion_tokens": 15, "total_tokens": 50}})
    result = run(handler)
    assert result["status"] == "available" and len(calls) == 1
    assert result["usage"]["total_tokens"] == 50 and result["pdf_sent"] is False


def test_http_error_does_not_log_echoed_key_or_follow_redirect():
    for status in (302, 401, 429, 500):
        result = run(lambda request: httpx.Response(status, json={"error": "test-secret"},
            headers={"Location": "https://example.com"}))
        assert result["status"] == "failed" and result["calls"] == 1
        assert "test-secret" not in json.dumps(result)


def test_timeout_does_not_retry_or_expose_exception():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("test-secret", request=request)
    result = run(handler)
    assert result["status"] == "connection_failed" and len(calls) == 1
    assert "test-secret" not in json.dumps(result)


def test_extra_fields_and_truncated_output_are_not_success():
    def response(value, finish="stop"):
        return httpx.Response(200, json={"choices": [{"finish_reason": finish,
            "message": {"content": json.dumps(value)}}], "usage": {"prompt_tokens": 30}})
    result = run(lambda request: response({**probe_module.EXPECTED, "extra": True}))
    assert result["status"] == "output_invalid" and result["usage"]["prompt_tokens"] == 30
    assert run(lambda request: response(probe_module.EXPECTED, "length"))["status"] == "output_incomplete"
