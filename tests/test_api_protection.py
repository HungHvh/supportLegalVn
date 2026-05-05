import pytest
from fastapi.testclient import TestClient
from app import app # Assuming main_api.py or app.py is the entry
from core.security import rate_limiter, llm_circuit_breaker
from unittest.mock import AsyncMock, patch

# Removed global client to use fixture with lifespan support
# client = TestClient(app)

@pytest.fixture
def client():
    """Fixture that triggers FastAPI lifespan and sets up a controlled pipeline."""
    from core.rag_pipeline import LegalRAGPipeline
    from unittest.mock import MagicMock
    
    # Setup a pipeline with mocked dependencies but real circuit breaker logic
    with patch("core.rag_pipeline.LegalRAGPipeline._get_client", return_value=MagicMock()):
        mock_retriever = MagicMock()
        mock_retriever.aretrieve = AsyncMock(return_value=[])
        
        pipeline = LegalRAGPipeline(retriever=mock_retriever)
        # Use a real client mock that we can patch later
        pipeline.client = MagicMock()
        pipeline.client.generate_content_async = AsyncMock()
        
        # Inject into app state
        app.state.pipeline = pipeline
        
        with TestClient(app) as c:
            yield c

@pytest.fixture(autouse=True)
def reset_security():
    """Reset rate limiter and circuit breaker before each test."""
    rate_limiter.cache.clear()
    llm_circuit_breaker.state = "CLOSED"
    llm_circuit_breaker.failure_count = 0

def test_rate_limit_ip(client):
    """Test that IP-based rate limit triggers after 10 requests."""
    # We use a mocked IP or just rely on localhost
    for i in range(10):
        response = client.post("/api/v1/ask", json={"query": "test", "chat_history": []})
        # We don't care about the result, just that it's not 429
        assert response.status_code != 429

    # 11th request should fail
    response = client.post("/api/v1/ask", json={"query": "test", "chat_history": []})
    assert response.status_code == 429
    assert "Too Many Requests" in response.json()["detail"]["error"]

def test_rate_limit_user(client):
    """Test that User-based rate limit triggers."""
    headers = {"X-User-ID": "user123"}
    for i in range(10):
        response = client.post("/api/v1/ask", json={"query": "test", "chat_history": []}, headers=headers)
        assert response.status_code != 429

    response = client.post("/api/v1/ask", json={"query": "test", "chat_history": []}, headers=headers)
    assert response.status_code == 429

def test_circuit_breaker_open(client):
    """Test that Circuit Breaker opens after multiple failures."""
    # Patch the async generator and call to fail
    app.state.pipeline.client.generate_content_async.side_effect = Exception("LLM Down")
    
    for i in range(5):
        client.post("/api/v1/ask", json={"query": "test", "chat_history": []})
        
    # After 5 failures, the circuit should be OPEN
    assert llm_circuit_breaker.state == "OPEN"
    
    # Next call should return 503 immediately
    response = client.post("/api/v1/ask", json={"query": "test", "chat_history": []})
    assert response.status_code == 503
    
    # Next call should return 503 immediately
    response = client.post("/api/v1/ask", json={"query": "test", "chat_history": []})
    assert response.status_code == 503
    assert "Service Unavailable" in response.json()["detail"]["error"]

def test_rate_limit_search_relaxed(client):
    """Test that search has a more relaxed limit (30)."""
    for i in range(30):
        response = client.post("/api/v1/search-articles", json={"query": "test"})
        assert response.status_code != 429

    response = client.post("/api/v1/search-articles", json={"query": "test"})
    assert response.status_code == 429
