import asyncio
import os
import pytest
from dotenv import load_dotenv
from core.rag_pipeline import LegalRAGPipeline, LegalHybridRetriever
from core.classifier import LegalQueryClassifier
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever
from unittest.mock import MagicMock

load_dotenv()

@pytest.mark.asyncio
async def test_pipeline_with_groq():
    """Verify pipeline works with Groq provider."""
    # Mock retrievers to avoid heavy setup
    async def mock_aretrieve(*args, **kwargs):
        return []
    
    v_retriever = MagicMock(spec=QdrantRetriever)
    v_retriever.aretrieve_with_filter = mock_aretrieve
    
    f_retriever = MagicMock(spec=SQLiteFTS5Retriever)
    f_retriever.aretrieve = mock_aretrieve
    
    classifier = LegalQueryClassifier()
    
    hybrid_retriever = LegalHybridRetriever(
        classifier=classifier,
        vector_retriever=v_retriever,
        fts_retriever=f_retriever
    )
    
    # Initialize pipeline with Groq
    pipeline = LegalRAGPipeline(
        retriever=hybrid_retriever,
        provider="groq",
        model_name="llama-3.1-8b-instant"
    )
    
    print(f"\nTesting Pipeline with Provider: {pipeline.client.__class__.__name__}")
    
    query = "Luật đất đai có quy định gì về bồi thường?"
    
    # Test regular query
    result = await pipeline.acustom_query(query)
    print(f"Answer length: {len(result['answer'])}")
    assert len(result['answer']) > 0
    
    # Test streaming query
    print("Testing streaming output...")
    tokens = []
    async for token in pipeline.astream_query(query):
        tokens.append(token)
    
    print(f"Received {len(tokens)} streaming tokens.")
    assert len(tokens) > 0
    print("[OK] Pipeline Groq integration verified.")

if __name__ == "__main__":
    asyncio.run(test_pipeline_with_groq())
