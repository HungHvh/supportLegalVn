from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
import pytest

from app import app


class FakeTextNode:
    def __init__(self, node_id, metadata, content):
        self.node_id = node_id
        self.id_ = node_id
        self.metadata = metadata
        self._content = content

    def get_content(self):
        return self._content


class FakeNodeWithScore:
    def __init__(self, node, score=1.0):
        self.node = node
        self.score = score


@pytest.fixture(autouse=True)
def mock_pipeline():
    # Replace the app.state.pipeline with a mock that has retriever and fts_retriever
    mock = MagicMock()
    mock.retriever = MagicMock()
    mock.retriever.aretrieve = AsyncMock()
    mock.retriever.fts_retriever = MagicMock()
    mock.retriever.fts_retriever.get_articles_by_uuids = AsyncMock()
    mock.retriever.fts_retriever.aretrieve_articles_by_title = AsyncMock()
    app.state.pipeline = mock
    return mock


def test_search_by_query_returns_results(mock_pipeline):
    node = FakeNodeWithScore(FakeTextNode("uuid-1", {"article_uuid": "uuid-1", "article_title": "Điều 1", "so_ky_hieu": "Văn bản A"}, "Nội dung điều 1"), score=0.9)
    mock_pipeline.retriever.fts_retriever.aretrieve_articles_by_title.return_value = [node]
    mock_pipeline.retriever.fts_retriever.get_articles_by_uuids.return_value = [node]

    client = TestClient(app)
    resp = client.post("/api/v1/search-articles", json={"query": "trộm cắp", "top_k": 5})
    assert resp.status_code == 200
    j = resp.json()
    assert j["top_results_count"] == 1
    assert j["results"][0]["article_uuid"] == "uuid-1"
    assert "full_content" in j["results"][0]


def test_search_by_uuid_fetches_article(mock_pipeline):
    node = FakeNodeWithScore(FakeTextNode("uuid-2", {"article_uuid": "uuid-2", "article_title": "Điều 2", "so_ky_hieu": "Văn bản B"}, "Nội dung điều 2"), score=1.0)
    mock_pipeline.retriever.fts_retriever.get_articles_by_uuids.return_value = [node]

    client = TestClient(app)
    resp = client.post("/api/v1/search-articles", json={"article_uuid": "uuid-2"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["top_results_count"] == 1
    assert j["results"][0]["article_uuid"] == "uuid-2"


def test_validation_error_when_no_query_or_uuid():
    client = TestClient(app)
    resp = client.post("/api/v1/search-articles", json={})
    assert resp.status_code == 400


def test_internal_exception_returns_500(mock_pipeline):
    mock_pipeline.retriever.fts_retriever.aretrieve_articles_by_title.side_effect = Exception("boom")
    client = TestClient(app)
    resp = client.post("/api/v1/search-articles", json={"query": "x"})
    assert resp.status_code == 500

