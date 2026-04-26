import pytest
from core.classifier import LegalQueryClassifier, QueryClassification

@pytest.mark.asyncio
async def test_classification_smoke():
    classifier = LegalQueryClassifier()
    # Mocking or using a real API key depends on environment
    # For now, we just ensure the interface is correct
    query = "Thủ tục đăng ký doanh nghiệp mới"
    result = await classifier.classify(query)
    
    assert isinstance(result, QueryClassification)
    assert len(result.domains) > 0
    assert 0 <= result.confidence <= 1.0

@pytest.mark.asyncio
async def test_classification_general():
    classifier = LegalQueryClassifier()
    query = "Hôm nay trời đẹp không?"
    result = await classifier.classify(query)
    
    # Low confidence or unrelated queries should fall back to General
    if result.confidence < 0.5:
        assert "General" in result.domains or len(result.domains) == 0
