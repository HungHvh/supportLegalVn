import pytest
import sqlite3
import uuid
import os
import sys
from unittest.mock import MagicMock
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["sentence_transformers"].__spec__ = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["torch"].__spec__ = MagicMock()

import indexer
from db.sqlite import init_db, get_db_connection, is_processed, mark_as_processed

class MockEmbedder:
    async def batch_get_embeddings(self, texts):
        return [[0.1] * 768 for _ in texts]

indexer.VietnameseSBERTProvider = MockEmbedder
indexer.SentenceTransformer = MagicMock()

@pytest.fixture
def mock_db():
    db_path = "test_legal.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    conn = get_db_connection(db_path)
    yield conn
    conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)

def test_idempotency_logic(mock_db):
    doc_id = "test_123"
    assert not is_processed(mock_db, doc_id)
    
    mark_as_processed(mock_db, doc_id)
    assert is_processed(mock_db, doc_id)

def test_chunking_logic():
    # Test logic for splitting
    from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
    
    headers_to_split_on = [("#", "H1")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    length_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=10)
    
    long_text = "# Header\n" + "a" * 200
    md_splits = md_splitter.split_text(long_text)
    
    assert len(md_splits) == 1
    assert len(md_splits[0].page_content) > 100
    
    sub_splits = length_splitter.split_text(md_splits[0].page_content)
    assert len(sub_splits) > 1
    for s in sub_splits:
        assert len(s) <= 120 # including overlap etc

@pytest.mark.asyncio
async def test_batch_processing_logic(mock_db):
    from indexer import process_batch
    from db.qdrant import QdrantManager
    
    # Mock services
    q_mgr = MagicMock()
    embed_provider = MockEmbedder()
    
    test_batch = [
        {
            "chunk_id": "c1",
            "doc_id": "d1",
            "so_ky_hieu": "SKH1",
            "headers": {"H1": "Title"},
            "content": "Test content"
        }
    ]
    
    await process_batch(test_batch, embed_provider, q_mgr, mock_db)
    
    # Verify SQLite entry
    cursor = mock_db.cursor()
    cursor.execute("SELECT doc_id FROM legal_documents WHERE doc_id = 'd1'")
    assert cursor.fetchone() is not None
    
    # Verify Qdrant call
    assert q_mgr.client.upsert.called
