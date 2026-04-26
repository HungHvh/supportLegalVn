import aiosqlite
from typing import List, Optional
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore, TextNode

class SQLiteFTS5Retriever(BaseRetriever):
    """Custom retriever that uses SQLite FTS5 for keyword search (Async)."""

    def __init__(self, db_path: str = "legal_poc.db", top_k: int = 10):
        self.db_path = db_path
        self.top_k = top_k
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Synchronous retrieve (deprecated in favor of _aretrieve)."""
        # This is kept for compatibility but should not be used in FastAPI
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # ... logic ... (omitted for brevity, referring to _aretrieve)
        return []

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Retrieve nodes from SQLite using FTS5 (Async)."""
        query_str = query_bundle.query_str
        
        sql = """
            SELECT 
                ld.doc_id, 
                ld.content, 
                ld.headers, 
                ld.domain, 
                ld.so_ky_hieu,
                fts.rank as score
            FROM docs_fts fts
            JOIN legal_documents ld ON ld.id = fts.rowid
            WHERE docs_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        
        nodes = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, (query_str, self.top_k)) as cursor:
                    rows = await cursor.fetchall()
                    
                    for row in rows:
                        metadata = {
                            "doc_id": row["doc_id"],
                            "domain": row["domain"],
                            "so_ky_hieu": row["so_ky_hieu"],
                            "headers": row["headers"]
                        }
                        node = TextNode(
                            text=row["content"],
                            metadata=metadata,
                            id_=row["doc_id"]
                        )
                        nodes.append(NodeWithScore(node=node, score=-row["score"]))
        except Exception as e:
            print(f"[Error] SQLite retrieval failed: {e}")
            
        return nodes

if __name__ == "__main__":
    import asyncio
    # Quick test
    async def test():
        retriever = SQLiteFTS5Retriever()
        results = await retriever.aretrieve("Luật đất đai")
        for res in results:
            print(f"Node ID: {res.node.node_id}, Score: {res.score}")
            print(f"Text snippet: {res.node.get_content()[:100]}...")

    asyncio.run(test())
