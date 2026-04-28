import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from google.api_core import exceptions
from tools.gemini_client import GeminiClient

@pytest.mark.asyncio
async def test_gemini_retry_success_eventually():
    """Verify that GeminiClient retries on ResourceExhausted and eventually succeeds."""
    client = GeminiClient(api_key="dummy")
    
    # Mock the internal model
    mock_model = MagicMock()
    client.model = mock_model
    
    # Create a side effect: fail twice, then succeed
    mock_response = MagicMock()
    mock_response.text = "Success!"
    
    client.model.generate_content_async = AsyncMock(side_effect=[
        exceptions.ResourceExhausted("Quota exceeded"),
        exceptions.ResourceExhausted("Quota exceeded"),
        mock_response
    ])
    
    # Call the method
    result = await client.generate_content_async("test prompt")
    
    assert result.text == "Success!"
    assert client.model.generate_content_async.call_count == 3

@pytest.mark.asyncio
async def test_gemini_retry_failure_after_max_attempts():
    """Verify that GeminiClient raises ResourceExhausted after max retries."""
    client = GeminiClient(api_key="dummy")
    
    mock_model = MagicMock()
    client.model = mock_model
    
    # Always fail
    client.model.generate_content_async = AsyncMock(side_effect=exceptions.ResourceExhausted("Quota exceeded"))
    
    with pytest.raises(exceptions.ResourceExhausted):
        await client.generate_content_async("test prompt")
    
    # tenacity is configured for 5 attempts
    assert client.model.generate_content_async.call_count == 5
