import aiosqlite
import re
from typing import List
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode

class SQLiteFTS5Retriever(BaseRetriever):
    """Custom retriever that uses SQLite FTS5 for chunk-level keyword search (Async)."""

    def __init__(self, db_path: str = "legal_poc.db", top_k: int = 50):
        self.db_path = db_path
        self.top_k = top_k
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Synchronous retrieve (deprecated)."""
        return []

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Retrieve chunk nodes from SQLite using chunks_fts (Async)."""
        query_str = query_bundle.query_str
        # Basic sanitization for FTS5
        safe_query = re.sub(r"[^\w\sÀ-ỹ]", " ", query_str).strip()
        if not safe_query:
            safe_query = query_str.strip()

        # Phase 10: Search in chunks_fts, join with legal_chunks
        sql = """
            SELECT 
                lc.chunk_id,
                lc.article_uuid,
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

        nodes = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, (safe_query, self.top_k)) as cursor:
                    rows = await cursor.fetchall()

                    for row in rows:
                        metadata = {
                            "chunk_id": row["chunk_id"],
                            "article_uuid": row["article_uuid"],
                            "so_ky_hieu": row["so_ky_hieu"],
                            "chunk_path": row["chunk_path"]
                        }
                        node = TextNode(
                            text=row["content"],
                            metadata=metadata,
                            id_=row["chunk_id"]
                        )
                        nodes.append(NodeWithScore(node=node, score=row["score"]))
        except Exception as e:
            print(f"[Error] SQLite FTS5 retrieval failed: {e}")

        return nodes
