import os
import asyncio
from typing import List, Optional
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode

class QdrantRetriever:
    """Wrapper for Qdrant vector search using native query API (Async)."""

    def __init__(
        self, 
        collection_name: str = "legal_chunks", 
        host: str = os.getenv("QDRANT_HOST", "localhost"), 
        port: int = int(os.getenv("QDRANT_PORT", 6333)),
        top_k: int = 10,
        embed_model_name: str = "keepitreal/vietnamese-sbert"
    ):
        try:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            self.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)
        except Exception as e:
            print(f"[Warning] Qdrant embed model unavailable: {e}")
            self.embed_model = None
        self._client = None
        self._client_host = host
        self._client_port = port
        self.collection_name = collection_name
        self.top_k = top_k

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from qdrant_client import AsyncQdrantClient
            self._client = AsyncQdrantClient(host=self._client_host, port=self._client_port)
        except Exception as e:
            print(f"[Warning] Qdrant client unavailable: {e}")
            self._client = None

        return self._client

    async def aretrieve_with_filter(
        self, 
        query: QueryBundle, 
        domains: Optional[List[str]] = None
    ) -> List[NodeWithScore]:
        """
        Directly query Qdrant.
        """
        if self.embed_model is None:
            return []

        client = self._get_client()
        if client is None:
            return []

        # 1. Generate embedding
        query_embedding = await self.embed_model.aget_query_embedding(query.query_str)
        
        # 2. Build filters
        query_filter = None
        if domains and "General" not in domains:
            from qdrant_client.http import models as qmodels
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="domain",
                        match=qmodels.MatchAny(any=domains)
                    )
                ]
            )

        # 3. Try different search methods based on client version
        hits = []
        try:
            # Method A: query_points (Modern)
            response = await client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                using="dense",
                query_filter=query_filter,
                limit=self.top_k,
                with_payload=True
            )
            hits = response.points
        except Exception as e:
            print(f"query_points failed: {e}")
            hits = []

        # 4. Convert to NodeWithScore
        nodes = []
        for hit in hits:
            payload = hit.payload or {}
            node = TextNode(
                text=payload.get("content", ""),
                id_=str(hit.id),
                metadata=payload
            )
            nodes.append(NodeWithScore(node=node, score=hit.score))
            
        return nodes

    def retrieve_with_filter(self, query: QueryBundle, domains: Optional[List[str]] = None) -> List[NodeWithScore]:
        """Synchronous convenience wrapper used by older tests."""
        return asyncio.run(self.aretrieve_with_filter(query, domains=domains))

    async def aretrieve(self, query_str: str) -> List[NodeWithScore]:
        """Simple string-based retrieval."""
        return await self.aretrieve_with_filter(QueryBundle(query_str))
