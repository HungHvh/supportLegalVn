import os
import asyncio
from typing import List, Optional
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode

from core.embeddings import SAFE_EMBEDDING_MODEL_NAME

class QdrantRetriever:
    """Wrapper for Qdrant vector search using native query API (Async)."""

    def __init__(
        self, 
        collection_name: str = "legal_chunks", 
        host: str = os.getenv("QDRANT_HOST", "localhost"), 
        port: int = int(os.getenv("QDRANT_PORT", 6333)),
        top_k: int = 50,
        embed_model_name: str = None
    ):
        requested_model = embed_model_name or os.getenv("EMBEDDING_MODEL_NAME", SAFE_EMBEDDING_MODEL_NAME)
        try:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            self.embed_model = HuggingFaceEmbedding(model_name=requested_model)
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
        Directly query Qdrant. (Phase 10: Returns chunk-level nodes)
        """
        if self.embed_model is None:
            return []

        client = self._get_client()
        if client is None:
            return []

        # 1. Generate embedding
        query_embedding = await self.embed_model.aget_query_embedding(query.query_str)
        
        # 2. Build filters (Note: domain might be handled differently in Phase 10 if needed)
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

        # 3. Search
        hits = []
        try:
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
            print(f"[Error] Qdrant search failed: {e}")
            hits = []

        # 4. Convert to NodeWithScore
        nodes = []
        for hit in hits:
            payload = hit.payload or {}
            # Phase 10 payload includes chunk_id, article_uuid, so_ky_hieu, level, article_title
            node = TextNode(
                text=payload.get("content", ""), # This might be missing in payload if we only store minimal, 
                                                 # so we'll fetch from SQLite later if needed, 
                                                 # but we'll try to keep content in payload for reranking if possible.
                id_=str(hit.id),
                metadata=payload
            )
            nodes.append(NodeWithScore(node=node, score=hit.score))
            
        return nodes

    async def aretrieve(self, query_str: str) -> List[NodeWithScore]:
        """Simple string-based retrieval."""
        return await self.aretrieve_with_filter(QueryBundle(query_str))
