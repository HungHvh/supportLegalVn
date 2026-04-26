import sys
from unittest.mock import MagicMock, AsyncMock

# Comprehensive mock list to bypass local DLL issues
problematic_modules = [
    "llama_index.embeddings.huggingface",
    "transformers",
    "torch",
    "onnxruntime",
    "fastembed",
    "qdrant_client",
    "llama_index.vector_stores.qdrant",
    "retrievers.qdrant_retriever",
    "retrievers.sqlite_retriever"
]

for mod in problematic_modules:
    sys.modules[mod] = MagicMock()

import pytest
from core.rag_pipeline import LegalHybridRetriever
from llama_index.core import QueryBundle

@pytest.mark.asyncio
async def test_retriever_ablation_logic():
    """Verify that ablation toggles correctly enable/disable retrieval paths."""
    
    # 1. Setup Mocks for dependencies of LegalHybridRetriever
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=MagicMock(domains=["General"]))
    
    # We pass these into the constructor
    mock_vector = MagicMock()
    mock_vector.aretrieve_with_filter = AsyncMock(return_value=[])
    
    mock_fts = MagicMock()
    mock_fts.aretrieve = AsyncMock(return_value=[])
    
    query = QueryBundle("test query")
    
    # 2. Test Case: Vector ONLY
    retriever_vector = LegalHybridRetriever(
        classifier=mock_classifier,
        vector_retriever=mock_vector,
        fts_retriever=mock_fts,
        use_vector=True,
        use_keyword=False,
        use_classifier=False
    )
    await retriever_vector.aretrieve(query)
    
    mock_vector.aretrieve_with_filter.assert_called()
    mock_fts.aretrieve.assert_not_called()
    mock_classifier.classify.assert_not_called()
    
    mock_vector.aretrieve_with_filter.reset_mock()
    mock_fts.aretrieve.reset_mock()
    mock_classifier.classify.reset_mock()
    
    # 3. Test Case: Keyword ONLY
    retriever_keyword = LegalHybridRetriever(
        classifier=mock_classifier,
        vector_retriever=mock_vector,
        fts_retriever=mock_fts,
        use_vector=False,
        use_keyword=True,
        use_classifier=False
    )
    await retriever_keyword.aretrieve(query)
    
    mock_vector.aretrieve_with_filter.assert_not_called()
    mock_fts.aretrieve.assert_called()
    
    mock_vector.aretrieve_with_filter.reset_mock()
    mock_fts.aretrieve.reset_mock()
    
    # 4. Test Case: Optimized (Hybrid + Classifier)
    retriever_optimized = LegalHybridRetriever(
        classifier=mock_classifier,
        vector_retriever=mock_vector,
        fts_retriever=mock_fts,
        use_vector=True,
        use_keyword=True,
        use_classifier=True
    )
    await retriever_optimized.aretrieve(query)
    
    mock_classifier.classify.assert_called_once()
    mock_vector.aretrieve_with_filter.assert_called_once()
    mock_fts.aretrieve.assert_called_once()
