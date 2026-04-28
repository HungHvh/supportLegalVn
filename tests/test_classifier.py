import pytest
from core.classifier import LegalQueryClassifier, QueryClassification

@pytest.mark.asyncio
async def test_classification_smoke():
    classifier = LegalQueryClassifier(provider="dashscope", fallback_provider="ollama")

    class MockResponse:
        text = '{"domains": ["Business & Commercial"], "confidence": 0.8, "is_explicit_filter": false}'

    async def mock_call_provider(provider_name, prompt):
        return MockResponse()

    classifier._call_provider = mock_call_provider

    query = "Thủ tục đăng ký doanh nghiệp mới"
    result = await classifier.classify(query)
    
    assert isinstance(result, QueryClassification)
    assert len(result.domains) > 0
    assert 0 <= result.confidence <= 1.0

@pytest.mark.asyncio
async def test_classification_general():
    classifier = LegalQueryClassifier(provider="dashscope", fallback_provider="ollama")

    async def always_fail(provider_name, prompt):
        raise RuntimeError("provider failure")

    classifier._call_provider = always_fail

    query = "Hôm nay trời đẹp không?"
    result = await classifier.classify(query)

    # Low confidence or unrelated queries should fall back to General
    if result.confidence < 0.5:
        assert "General" in result.domains or len(result.domains) == 0
