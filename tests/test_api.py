import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app import app

client = TestClient(app)

@pytest.fixture
def mock_pipeline():
    mock = MagicMock()
    mock.acustom_query = AsyncMock(return_value={
        "answer": "Test Answer",
        "citations": [{"source": "Doc 1", "text": "Snippet", "score": 0.9}],
        "detected_domains": ["Civil"],
        "confidence_score": 0.95
    })
    
    async def mock_stream(query):
        yield "Token1 "
        yield "Token2"
        
    mock.astream_query = mock_stream
    return mock

def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ask(mock_pipeline):
    # Mock the app state
    app.state.pipeline = mock_pipeline
    
    response = client.post("/api/v1/ask", json={"query": "test query"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Test Answer"
    assert len(data["citations"]) == 1

def test_stream(mock_pipeline):
    app.state.pipeline = mock_pipeline
    
    with client.stream("POST", "/api/v1/stream", json={"query": "test query"}) as response:
        assert response.status_code == 200
        # SSE responses are text/event-stream
        lines = [line.decode("utf-8") if isinstance(line, bytes) else line for line in response.iter_lines() if line]
        assert len(lines) >= 2
        # Check first frame (event + data)
        assert "event: message" in lines[0]
        assert "data:" in lines[1]
        assert "Token1" in lines[1]
