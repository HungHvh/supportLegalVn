import os
import asyncio
from typing import List, Optional
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

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
        self.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)
        self.client = AsyncQdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.top_k = top_k

    async def aretrieve_with_filter(
        self, 
        query: QueryBundle, 
        domains: Optional[List[str]] = None
    ) -> List[NodeWithScore]:
        """
        Directly query Qdrant.
        """
        # 1. Generate embedding
        query_embedding = await self.embed_model.aget_query_embedding(query.query_str)
        
        # 2. Build filters
        query_filter = None
        if domains and "General" not in domains:
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
            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                using="dense",
                query_filter=query_filter,
                limit=self.top_k,
                with_payload=True
            )
            hits = response.points
        except Exception as e:
            print(f"query_points failed, trying search_points: {e}")
            try:
                # Method B: search_points (Legacy)
                hits = await self.client.search(
                    collection_name=self.collection_name,
                    query_vector=("dense", query_embedding),
                    query_filter=query_filter,
                    limit=self.top_k,
                    with_payload=True
                )
            except Exception as e2:
                print(f"search failed too: {e2}")
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

    async def aretrieve(self, query_str: str) -> List[NodeWithScore]:
        """Simple string-based retrieval."""
        return await self.aretrieve_with_filter(QueryBundle(query_str))
