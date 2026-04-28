import pytest

from core.classifier import LegalQueryClassifier


class MockResponse:
    def __init__(self, text: str):
        self.text = text


@pytest.mark.asyncio
async def test_primary_provider_success():
    classifier = LegalQueryClassifier(provider="dashscope", fallback_provider="ollama")

    async def mock_call(provider_name, prompt):
        assert provider_name == "dashscope"
        return MockResponse('{"domains": ["Criminal"], "confidence": 0.9, "is_explicit_filter": false}')

    classifier._call_provider = mock_call
    result = await classifier.classify("Tội danh lừa đảo là gì?")

    assert result.domains == ["Criminal"]
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_primary_failure_backup_success():
    classifier = LegalQueryClassifier(provider="dashscope", fallback_provider="ollama")

    async def mock_call(provider_name, prompt):
        if provider_name == "dashscope":
            raise RuntimeError("dashscope timeout")
        return MockResponse('{"domains": ["Land & Real Estate"], "confidence": 0.77, "is_explicit_filter": false}')

    classifier._call_provider = mock_call
    result = await classifier.classify("Tranh chấp sổ đỏ giải quyết sao?")

    assert result.domains == ["Land & Real Estate"]
    assert result.confidence == 0.77


@pytest.mark.asyncio
async def test_both_provider_failures_fallback_general():
    classifier = LegalQueryClassifier(provider="dashscope", fallback_provider="ollama")

    async def mock_call(provider_name, prompt):
        raise RuntimeError("all providers down")

    classifier._call_provider = mock_call
    result = await classifier.classify("Câu hỏi ngoài phạm vi")

    assert result.domains == ["General"]
    assert result.confidence == 0.0
    assert result.is_explicit_filter is False


@pytest.mark.asyncio
async def test_malformed_json_fallback_general():
    classifier = LegalQueryClassifier(provider="dashscope", fallback_provider="ollama")

    async def mock_call(provider_name, prompt):
        return MockResponse("not-json")

    classifier._call_provider = mock_call
    result = await classifier.classify("Thử parse lỗi")

    assert result.domains == ["General"]
    assert result.confidence == 0.0

