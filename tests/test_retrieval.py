import pytest
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from retrievers.qdrant_retriever import QdrantRetriever
from llama_index.core import QueryBundle

def test_sqlite_retriever_smoke():
    retriever = SQLiteFTS5Retriever(db_path="legal_data.db")
    query = QueryBundle("quy định về bảo hiểm xã hội")
    nodes = retriever._retrieve(query)
    
    assert isinstance(nodes, list)
    if nodes:
        assert hasattr(nodes[0], "node")
        assert hasattr(nodes[0], "score")

def test_qdrant_retriever_filtering():
    retriever = QdrantRetriever(collection_name="legal_chunks")
    query = QueryBundle("quy định về thuế")
    # Test with domain filter
    nodes = retriever.retrieve_with_filter(query, domains=["Administrative & Tax"])
    
    assert isinstance(nodes, list)
    # Metadata check would go here if we had a mock client
