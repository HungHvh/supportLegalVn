import os
from typing import List, Optional

from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode

from core.embeddings import SAFE_EMBEDDING_MODEL_NAME


class QdrantRetriever:
    """
    Wrapper for Qdrant vector search.

    This version supports two retrieval modes:
    1. Article-level retrieval from the `legal_articles` collection.
    2. Chunk-level retrieval from the legacy `legal_chunks` collection.

    The article-level search is the primary path for the new legal pipeline.
    """

    def __init__(
        self,
        collection_name: str = "legal_articles",
        host: str = os.getenv("QDRANT_HOST", "localhost"),
        port: int = int(os.getenv("QDRANT_PORT", 6333)),
        top_k: int = 50,
        embed_model_name: str = None,
    ):
        requested_model = embed_model_name or os.getenv(
            "EMBEDDING_MODEL_NAME", SAFE_EMBEDDING_MODEL_NAME
        )

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

            self._client = AsyncQdrantClient(
                host=self._client_host,
                port=self._client_port,
            )
        except Exception as e:
            print(f"[Warning] Qdrant client unavailable: {e}")
            self._client = None

        return self._client

    async def _embed_query(self, query_str: str):
        if self.embed_model is None:
            return None
        return await self.embed_model.aget_query_embedding(query_str)

    async def aretrieve_articles(
        self,
        query: QueryBundle,
        top_k: Optional[int] = None,
    ) -> List[NodeWithScore]:
        """
        Primary path:
        Search the `legal_articles` collection and return article-level nodes.
        """
        if self.embed_model is None:
            return []

        client = self._get_client()
        if client is None:
            return []

        query_embedding = await self._embed_query(query.query_str)
        if query_embedding is None:
            return []

        limit = top_k or self.top_k

        try:
            response = await client.query_points(
                collection_name="legal_articles",
                query=query_embedding,
                using="dense",
                limit=limit,
                with_payload=True,  # TODO: cót hể để false rồi query DB (trả về hết content)
            )
            hits = response.points
        except Exception as e:
            print(f"[Error] Qdrant article search failed: {e}")
            return []

        nodes: List[NodeWithScore] = []
        for hit in hits:
            payload = hit.payload or {}

            metadata = {
                "article_uuid": payload.get("article_uuid", str(hit.id)),
                "doc_id": payload.get("doc_id"),
                "so_ky_hieu": payload.get("so_ky_hieu"),
                "article_title": payload.get("article_title"),
                "article_path": payload.get("article_path"),
                "type": "ARTICLE",
            }

            node = TextNode(
                text=payload.get("full_content", ""),
                id_=str(payload.get("article_uuid", hit.id)),
                metadata=metadata,
            )
            nodes.append(NodeWithScore(node=node, score=hit.score))

        return nodes

    async def aretrieve_with_filter(
        self,
        query: QueryBundle,
        domains: Optional[List[str]] = None,
    ) -> List[NodeWithScore]:
        """
        Legacy / fallback path:
        Search the configured collection (default: legal_chunks).

        This is still kept for compatibility with older code paths.
        """
        if self.embed_model is None:
            return []

        client = self._get_client()
        if client is None:
            return []

        query_embedding = await self._embed_query(query.query_str)
        if query_embedding is None:
            return []

        query_filter = None
        if domains and "General" not in domains:
            from qdrant_client.http import models as qmodels

            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="domain",
                        match=qmodels.MatchAny(any=domains),
                    )
                ]
            )

        try:
            response = await client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                using="dense",
                query_filter=query_filter,
                limit=self.top_k,
                with_payload=True,
            )
            hits = response.points
        except Exception as e:
            print(f"[Error] Qdrant search failed: {e}")
            return []

        nodes: List[NodeWithScore] = []
        for hit in hits:
            payload = hit.payload or {}

            metadata = dict(payload)
            metadata.setdefault("type", "CHUNK")

            node = TextNode(
                text=payload.get("content", ""),
                id_=str(hit.id),
                metadata=metadata,
            )
            nodes.append(NodeWithScore(node=node, score=hit.score))

        return nodes

    async def aretrieve(self, query_str: str) -> List[NodeWithScore]:
        """Simple string-based retrieval against the configured collection."""
        return await self.aretrieve_with_filter(QueryBundle(query_str))
