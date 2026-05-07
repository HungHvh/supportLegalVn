import json

import pytest
import httpx

import tools.groq_client as groq_module
from tools.groq_client import GroqClient


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, payload=None, lines=None):
        self.status_code = status_code
        self._payload = payload or {}
        self._lines = lines or []
        self.request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request, content=json.dumps(self._payload).encode("utf-8"))
            response.raise_for_status()

    def json(self):
        return self._payload

    async def aread(self):
        return json.dumps(self._payload).encode("utf-8")

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamContext:
    def __init__(self, response: _FakeResponse):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.post_calls = []
        self.stream_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        self.post_calls.append((url, json, headers))
        return _FakeResponse(payload={"choices": [{"message": {"content": "OK"}}]})

    def stream(self, method, url, json, headers):
        self.stream_calls.append((method, url, json, headers))
        response = _FakeResponse(
            payload={},
            lines=[
                'data: {"choices": [{"delta": {"content": "Xin chào"}}]}',
                "data: [DONE]",
            ],
        )
        return _FakeStreamContext(response)


@pytest.mark.asyncio
async def test_groq_client_uses_safe_default_model_and_payload(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    fake_client = _FakeAsyncClient()
    monkeypatch.setattr(groq_module.httpx, "AsyncClient", lambda timeout=None: fake_client)

    client = GroqClient()
    result = await client.generate_content_async(
        "Xin chào",
        temperature=0.2,
        max_tokens=128,
        system_instruction="Bạn là trợ lý pháp luật.",
    )

    assert result.text == "OK"
    assert fake_client.post_calls
    _, payload, headers = fake_client.post_calls[0]
    assert payload["model"] == "llama-3.1-8b-instant"
    assert payload["stream"] is False
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 128
    assert payload["messages"][0] == {"role": "system", "content": "Bạn là trợ lý pháp luật."}
    assert payload["messages"][1] == {"role": "user", "content": "Xin chào"}
    assert headers["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_groq_streaming_uses_same_payload_shape(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    fake_client = _FakeAsyncClient()
    monkeypatch.setattr(groq_module.httpx, "AsyncClient", lambda timeout=None: fake_client)

    client = GroqClient()
    chunks = []
    async for chunk in client.astream_query("Xin chào"):
        chunks.append(chunk.text)

    assert chunks == ["Xin chào"]
    assert fake_client.stream_calls
    method, url, payload, headers = fake_client.stream_calls[0]
    assert method == "POST"
    assert url.endswith("/chat/completions")
    assert payload["model"] == "llama-3.1-8b-instant"
    assert payload["stream"] is True
    assert payload["messages"][1] == {"role": "user", "content": "Xin chào"}
    assert headers["Authorization"] == "Bearer test-key"


