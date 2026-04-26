import os
from typing import List, Optional
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext, QueryBundle, Settings
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from qdrant_client import AsyncQdrantClient

class QdrantRetriever:
    """Wrapper for Qdrant vector search with metadata filtering (Async)."""

    def __init__(
        self, 
        collection_name: str = "legal_chunks", 
        host: str = os.getenv("QDRANT_HOST", "localhost"), 
        port: int = int(os.getenv("QDRANT_PORT", 6333)),
        top_k: int = 10,
        embed_model_name: str = "keepitreal/vietnamese-sbert"
    ):
        # Configure embedding model globally for this instance context
        Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)
        
        self.client = AsyncQdrantClient(host=host, port=port)
        self.vector_store = QdrantVectorStore(
            aclient=self.client, 
            collection_name=collection_name
        )
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        self.index = VectorStoreIndex.from_vector_store(
            self.vector_store, 
            storage_context=self.storage_context
        )
        self.top_k = top_k

    async def aretrieve_with_filter(
        self, 
        query: QueryBundle, 
        domains: Optional[List[str]] = None
    ) -> List[NodeWithScore]:
        """
        Retrieve nodes with optional domain filtering (Async).
        If 'General' is in domains, or domains is empty, no filter is applied.
        """
        filters = None
        if domains and "General" not in domains:
            # Multi-label filter: domain matches any in the list
            filters = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="domain", 
                        value=domains, 
                        operator=FilterOperator.IN
                    )
                ]
            )
            
        retriever = self.index.as_retriever(
            similarity_top_k=self.top_k,
            filters=filters
        )
        return await retriever.aretrieve(query)

if __name__ == "__main__":
    import asyncio
    # Quick test
    from llama_index.core import QueryBundle
    
    async def test():
        retriever = QdrantRetriever()
        query = QueryBundle("quy định về ly hôn")
        # Test without filter
        print("--- No Filter ---")
        results = await retriever.aretrieve_with_filter(query)
        for res in results:
            print(f"Node ID: {res.node.node_id}, Score: {res.score}, Domain: {res.node.metadata.get('domain')}")
            
        # Test with filter
        print("\n--- With Filter (Civil & Family) ---")
        results = await retriever.aretrieve_with_filter(query, domains=["Civil & Family"])
        for res in results:
            print(f"Node ID: {res.node.node_id}, Score: {res.score}, Domain: {res.node.metadata.get('domain')}")

    asyncio.run(test())
