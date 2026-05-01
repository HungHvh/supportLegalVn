import aiosqlite
import re
from typing import List, Optional

from llama_index.core import QueryBundle
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode


class SQLiteFTS5Retriever(BaseRetriever):
    """
    SQLite helper retriever.

    New primary use:
    - fetch chunks by article_uuid after article-level retrieval.

    Legacy use:
    - chunk-level FTS5 search via chunks_fts.
    """

    def __init__(self, db_path: str = "legal_poc.db", top_k: int = 50):
        self.db_path = db_path
        self.top_k = top_k
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Synchronous retrieve (deprecated)."""
        return []

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Legacy chunk-level search using FTS5."""
        query_str = query_bundle.query_str

        # Basic sanitization for FTS5
        safe_query = re.sub(r"[^\w\sÀ-ỹ]", " ", query_str).strip()
        if not safe_query:
            safe_query = query_str.strip()

        sql = """
            SELECT 
                lc.chunk_id,
                lc.article_uuid,
                lc.doc_id,
                lc.so_ky_hieu,
                lc.chunk_path,
                lc.content,
                -bm25(chunks_fts) AS score
            FROM chunks_fts fts
            JOIN legal_chunks lc ON lc.chunk_id = fts.chunk_id
            WHERE chunks_fts MATCH ?
            ORDER BY score DESC
            LIMIT ?
        """

        nodes: List[NodeWithScore] = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, (safe_query, self.top_k)) as cursor:
                    rows = await cursor.fetchall()

                    for row in rows:
                        metadata = {
                            "chunk_id": row["chunk_id"],
                            "article_uuid": row["article_uuid"],
                            "doc_id": row["doc_id"],
                            "so_ky_hieu": row["so_ky_hieu"],
                            "chunk_path": row["chunk_path"],
                            "type": "CHUNK",
                        }
                        node = TextNode(
                            text=row["content"],
                            metadata=metadata,
                            id_=row["chunk_id"],
                        )
                        nodes.append(NodeWithScore(node=node, score=row["score"]))
        except Exception as e:
            print(f"[Error] SQLite FTS5 retrieval failed: {e}")

        return nodes

    async def aretrieve(self, query_str: str) -> List[NodeWithScore]:
        """Convenience wrapper for legacy FTS5 search."""
        return await self._aretrieve(QueryBundle(query_str))

    async def get_chunks_by_articles(
        self,
        article_uuids: List[str],
        limit: Optional[int] = 200,
    ) -> List[NodeWithScore]:
        """
        Fetch chunks that belong to the given list of article UUIDs.

        This is the key helper for the article-first retrieval flow.
        """
        if not article_uuids:
            return []

        # Deduplicate while preserving order.
        seen = set()
        unique_article_uuids = []
        for aid in article_uuids:
            if aid and aid not in seen:
                seen.add(aid)
                unique_article_uuids.append(aid)

        if not unique_article_uuids:
            return []

        placeholders = ",".join("?" * len(unique_article_uuids))
        sql = f"""
            SELECT
                chunk_id,
                article_uuid,
                doc_id,
                so_ky_hieu,
                chunk_path,
                content
            FROM legal_chunks
            WHERE article_uuid IN ({placeholders})
            ORDER BY article_uuid, chunk_path, chunk_id
        """

        params = list(unique_article_uuids)

        nodes: List[NodeWithScore] = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()

                    for row in rows:
                        metadata = {
                            "chunk_id": row["chunk_id"],
                            "article_uuid": row["article_uuid"],
                            "doc_id": row["doc_id"],
                            "so_ky_hieu": row["so_ky_hieu"],
                            "chunk_path": row["chunk_path"],
                            "type": "CHUNK",
                        }
                        node = TextNode(
                            text=row["content"],
                            metadata=metadata,
                            id_=row["chunk_id"],
                        )
                        nodes.append(NodeWithScore(node=node, score=1.0))

                        if limit is not None and len(nodes) >= limit:
                            return nodes
        except Exception as e:
            print(f"[Error] SQLite article-chunk fetch failed: {e}")

        return nodes

    async def get_articles_by_uuids(
        self,
        article_uuids: List[str],
    ) -> List[NodeWithScore]:
        """
        Fetch full article rows from SQLite.

        This is useful when you want canonical article text from the DB
        instead of relying on Qdrant payloads.
        """
        if not article_uuids:
            return []

        seen = set()
        unique_article_uuids = []
        for aid in article_uuids:
            if aid and aid not in seen:
                seen.add(aid)
                unique_article_uuids.append(aid)

        if not unique_article_uuids:
            return []

        placeholders = ",".join("?" * len(unique_article_uuids))
        sql = f"""
            SELECT
                article_uuid,
                doc_id,
                so_ky_hieu,
                article_title,
                article_path,
                full_content
            FROM legal_articles
            WHERE article_uuid IN ({placeholders})
        """

        nodes: List[NodeWithScore] = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, unique_article_uuids) as cursor:
                    rows = await cursor.fetchall()

                    for row in rows:
                        metadata = {
                            "article_uuid": row["article_uuid"],
                            "doc_id": row["doc_id"],
                            "so_ky_hieu": row["so_ky_hieu"],
                            "article_title": row["article_title"],
                            "article_path": row["article_path"],
                            "type": "ARTICLE",
                        }
                        node = TextNode(
                            text=row["full_content"],
                            metadata=metadata,
                            id_=row["article_uuid"],
                        )
                        nodes.append(NodeWithScore(node=node, score=1.0))
        except Exception as e:
            print(f"[Error] SQLite article fetch failed: {e}")

        return nodes
