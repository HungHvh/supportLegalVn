import aiosqlite
import re
import time
from typing import List, Optional

from llama_index.core import QueryBundle
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode


class SQLiteFTS5Retriever(BaseRetriever):
    """
    SQLite helper retriever.

    New primary use:
    - BM25 search on article title (article-level candidates).
    - fetch chunks by article_uuid only for the legacy fallback.

    Legacy use:
    - chunk-level FTS5 search via chunks_fts.
    """

    def __init__(self, db_path: str = "legal_poc.db", top_k: int = 50):
        self.db_path = db_path
        self.top_k = top_k
        self._article_fts_table: Optional[str] = None
        self._chunk_fts_table: Optional[str] = None
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Synchronous retrieve (deprecated)."""
        return []

    def _sanitize_query(self, query_str: str) -> str:
        safe_query = re.sub(r"[^\w\sÀ-ỹ]", " ", query_str).strip()
        return safe_query or query_str.strip()

    async def _table_exists(self, db: aiosqlite.Connection, table_name: str) -> bool:
        async with db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
            (table_name,),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def _resolve_fts_table(
        self,
        db: aiosqlite.Connection,
        candidates: List[str],
        cache_attr: str,
    ) -> Optional[str]:
        cached = getattr(self, cache_attr)
        if cached:
            return cached

        for table_name in candidates:
            if await self._table_exists(db, table_name):
                setattr(self, cache_attr, table_name)
                return table_name

        return None

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Legacy chunk-level search using FTS5."""
        query_str = query_bundle.query_str
        safe_query = self._sanitize_query(query_str)

        nodes: List[NodeWithScore] = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                chunk_table = await self._resolve_fts_table(
                    db,
                    candidates=["chunks_fts"],
                    cache_attr="_chunk_fts_table",
                )
                if not chunk_table:
                    return []

                sql = f"""
                    SELECT 
                        lc.chunk_id,
                        lc.article_uuid,
                        lc.doc_id,
                        lc.so_ky_hieu,
                        lc.chunk_path,
                        lc.content,
                        -bm25({chunk_table}) AS score
                    FROM {chunk_table} fts
                    JOIN legal_chunks lc ON lc.chunk_id = fts.chunk_id
                    WHERE {chunk_table} MATCH ?
                    ORDER BY score DESC
                    LIMIT ?
                """

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
                        nodes.append(NodeWithScore(node=node, score=float(row["score"])))
        except Exception as e:
            print(f"[Error] SQLite FTS5 retrieval failed: {e}")

        return nodes

    async def aretrieve(self, query_str: str) -> List[NodeWithScore]:
        """Convenience wrapper for legacy FTS5 chunk search."""
        return await self._aretrieve(QueryBundle(query_str))

    async def aretrieve_articles_by_title(
        self,
        query_str: str,
        top_k: Optional[int] = None,
    ) -> List[NodeWithScore]:
        """
        Primary keyword path for article candidates.

        This expects an FTS5 table that indexes article titles and stores article_uuid.
        Common table name used by the indexer: `article_titles_fts`.
        """
        safe_query = self._sanitize_query(query_str)
        limit = top_k or self.top_k

        nodes: List[NodeWithScore] = []
        start_time = time.time()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                article_table = await self._resolve_fts_table(
                    db,
                    candidates=[
                        "article_titles_fts",
                        "article_title_fts",
                        "legal_article_titles_fts",
                        "articles_title_fts",
                        "articles_fts",
                    ],
                    cache_attr="_article_fts_table",
                )
                if not article_table:
                    return []

                sql = f"""
                    SELECT
                        la.article_uuid,
                        la.doc_id,
                        la.so_ky_hieu,
                        la.article_title,
                        la.article_path,
                        -bm25({article_table}) AS score
                    FROM {article_table} fts
                    JOIN legal_articles la ON la.article_uuid = fts.article_uuid
                    WHERE {article_table} MATCH ?
                    ORDER BY score DESC
                    LIMIT ?
                """

                async with db.execute(sql, (safe_query, limit)) as cursor:
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
                            # Candidate stage is metadata-only; full content is hydrated later.
                            text=row["article_title"] or row["so_ky_hieu"] or "",
                            metadata=metadata,
                            id_=row["article_uuid"],
                        )
                        nodes.append(NodeWithScore(node=node, score=float(row["score"])))
        except Exception as e:
            print(f"[Error] SQLite article title BM25 retrieval failed: {e}")

        print(
            "[SQLiteFTS5Retriever] Title BM25 took "
            f"{time.time() - start_time:.2f}s, hits: {len(nodes)}"
        )
        return nodes

    async def get_chunks_by_articles(
        self,
        article_uuids: List[str],
        limit: Optional[int] = 200,
    ) -> List[NodeWithScore]:
        """
        Fetch chunks that belong to the given list of article UUIDs.

        Used only by the legacy fallback.
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
        if limit is not None:
            sql += " LIMIT ?"

        nodes: List[NodeWithScore] = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                params = tuple(unique_article_uuids)
                if limit is not None:
                    params = params + (limit,)

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
        except Exception as e:
            print(f"[Error] SQLite chunk fetch by article_uuid failed: {e}")

        return nodes

    async def get_articles_by_uuids(self, article_uuids: List[str]) -> List[NodeWithScore]:
        """
        Fetch canonical article rows from SQLite.
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
                async with db.execute(sql, tuple(unique_article_uuids)) as cursor:
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
                            text=row["full_content"] or "",
                            metadata=metadata,
                            id_=row["article_uuid"],
                        )
                        nodes.append(NodeWithScore(node=node, score=1.0))
        except Exception as e:
            print(f"[Error] SQLite article fetch failed: {e}")

        return nodes
