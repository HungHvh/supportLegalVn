import pytest
import asyncio
from indexer import process_batch
from db.qdrant import QdrantManager
from core.embeddings import VietnameseSBERTProvider, HybridEmbeddingProvider
from qdrant_client.http import models

@pytest.mark.asyncio
async def test_qdrant_hybrid_upsert():
    """Verify that points are upserted with both dense and sparse vectors."""
    q_mgr = QdrantManager()
    collection_name = "test_hybrid_collection"
    
    # Ensure fresh collection
    if q_mgr.client.collection_exists(collection_name):
        q_mgr.client.delete_collection(collection_name)
    q_mgr.init_collection(collection_name)
    
    dense_provider = VietnameseSBERTProvider()
    hybrid_provider = HybridEmbeddingProvider(dense_provider)
    
    # Sample chunk
    test_id = "00000000-0000-0000-0000-000000000001"
    batch = [{
        "chunk_id": test_id,
        "doc_id": "123",
        "so_ky_hieu": "12/2024/QH15",
        "full_path": "Luật A > Điều 1",
        "level": "ĐIỀU",
        "content": "Nội dung điều 1",
        "content_for_embedding": "[Luật A > Điều 1] \n Nội dung điều 1"
    }]
    
    # Mock SQLite conn or use a dummy
    import sqlite3
    db_conn = sqlite3.connect(":memory:")
    db_conn.execute("CREATE TABLE legal_documents (doc_id TEXT, so_ky_hieu TEXT, full_path TEXT, content TEXT)")
    db_conn.execute("CREATE TABLE indexing_status (doc_id TEXT PRIMARY KEY)")
    
    # Override COLLECTION_NAME for test
    import indexer
    original_col = indexer.COLLECTION_NAME
    indexer.COLLECTION_NAME = collection_name
    
    try:
        await process_batch(batch, ["123"], hybrid_provider, q_mgr, db_conn)
        
        # Verify in Qdrant
        point = q_mgr.client.retrieve(collection_name=collection_name, ids=[test_id], with_vectors=True)[0]
        assert "dense" in point.vector
        assert "sparse" in point.vector
        assert point.payload["full_path"] == "Luật A > Điều 1"
        
    finally:
        indexer.COLLECTION_NAME = original_col
        q_mgr.client.delete_collection(collection_name)
        db_conn.close()

if __name__ == "__main__":
    asyncio.run(test_qdrant_hybrid_upsert())
