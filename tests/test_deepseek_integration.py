import pytest
from unittest.mock import AsyncMock, patch
from core.classifier import LegalQueryClassifier, QueryClassification
from tools.deepseek_client import DeepSeekResponse

@pytest.mark.asyncio
async def test_deepseek_classification_success():
    """Test successful classification using DeepSeek provider."""
    # Mock DeepSeekClient.generate_content_async
    mock_response = DeepSeekResponse(
        text='{"domains": ["Criminal"], "confidence": 0.95, "is_explicit_filter": false}'
    )
    
    with patch("tools.deepseek_client.DeepSeekClient.generate_content_async", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        
        classifier = LegalQueryClassifier(provider="deepseek", api_key="test_key")
        result = await classifier.classify("Ăn trộm bị phạt bao nhiêu năm tù?")
        
        assert isinstance(result, QueryClassification)
        assert "Criminal" in result.domains
        assert result.confidence == 0.95
        assert result.is_explicit_filter is False
        mock_gen.assert_called_once()

@pytest.mark.asyncio
async def test_deepseek_failover_to_gemini():
    """Test failover from DeepSeek to Gemini when DeepSeek fails."""
    # Mock DeepSeekClient to raise an exception
    # Mock GeminiClient to return success
    mock_gemini_response = AsyncMock()
    mock_gemini_response.text = '{"domains": ["Land & Real Estate"], "confidence": 0.8, "is_explicit_filter": true}'
    
    with patch("tools.deepseek_client.DeepSeekClient.generate_content_async", side_effect=Exception("DeepSeek API Down")):
        with patch("tools.gemini_client.GeminiClient.generate_content_async", new_callable=AsyncMock) as mock_gemini_gen:
            mock_gemini_gen.return_value = mock_gemini_response
            
            # Initialize with deepseek as primary, gemini as fallback
            classifier = LegalQueryClassifier(provider="deepseek", fallback_provider="gemini", api_key="test_key")
            
            # We need to mock the env for GeminiClient if not present
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test_gemini_key"}):
                result = await classifier.classify("Thủ tục làm sổ đỏ như thế nào?")
            
            assert "Land & Real Estate" in result.domains
            assert result.is_explicit_filter is True
            mock_gemini_gen.assert_called_once()
