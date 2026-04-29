import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import indexer
from core.parser import LegalNode, LegalLevel
from db.sqlite import init_db as real_init_db, get_db_connection as real_get_db_connection


def check_tree_helpers() -> None:
    root = LegalNode(
        level=LegalLevel.DOCUMENT,
        title="DOC",
        content="Root content",
        full_path="DOC",
        children=[
            LegalNode(
                level=LegalLevel.ARTICLE,
                title="Điều 1.",
                content="Article content",
                full_path="DOC > Điều 1.",
                children=[
                    LegalNode(
                        level=LegalLevel.CLAUSE,
                        title="Khoản 1.",
                        content="Clause 1",
                        full_path="DOC > Điều 1. > Khoản 1.",
                        children=[],
                    ),
                    LegalNode(
                        level=LegalLevel.CLAUSE,
                        title="Khoản 2.",
                        content="Clause 2",
                        full_path="DOC > Điều 1. > Khoản 2.",
                        children=[],
                    ),
                ],
            )
        ],
    )

    flattened = indexer.flatten_article_content(root.children[0])
    assert "Article content" in flattened
    assert "Khoản 1." in flattened
    assert "Clause 2" in flattened

    articles, chunks = indexer.collect_article_chunks(root, "42", "SKH-42")
    assert len(articles) == 1
    assert len(chunks) >= 1
    assert all(chunk["article_uuid"] == articles[0]["article_uuid"] for chunk in chunks)


async def check_process_batch() -> None:
    db_path = tempfile.mktemp(suffix=".db")
    original_sqlite_path = os.environ.get("SQLITE_DB_PATH")
    os.environ["SQLITE_DB_PATH"] = db_path
    real_init_db(db_path)
    conn = real_get_db_connection(db_path)

    class FakeClient:
        def __init__(self):
            self.calls = []

        def upsert(self, **kwargs):
            self.calls.append(kwargs)

    class FakeQMgr:
        def __init__(self):
            self.client = FakeClient()

    class FakeEmbedder:
        async def get_hybrid_embeddings(self, texts):
            return [{"dense": [float(i)], "sparse": []} for i, _ in enumerate(texts)]

    q_mgr = FakeQMgr()
    articles = [
        {"article_uuid": "a1", "doc_id": "1", "so_ky_hieu": "SKH-1", "article_title": "A1", "article_path": "P1", "full_content": "FC1"},
        {"article_uuid": "a2", "doc_id": "2", "so_ky_hieu": "SKH-2", "article_title": "A2", "article_path": "P2", "full_content": "FC2"},
    ]
    chunks = [
        {"chunk_id": "c1", "article_uuid": "a1", "doc_id": "1", "so_ky_hieu": "SKH-1", "level": "KHOẢN", "chunk_path": "P1", "content": "T1", "enriched_text": "[P1] T1", "article_title": "A1"},
        {"chunk_id": "c2", "article_uuid": "a2", "doc_id": "2", "so_ky_hieu": "SKH-2", "level": "KHOẢN", "chunk_path": "P2", "content": "T2", "enriched_text": "[P2] T2", "article_title": "A2"},
    ]

    original_batch = indexer.QDRANT_UPSERT_BATCH_SIZE
    indexer.QDRANT_UPSERT_BATCH_SIZE = 1
    try:
        await indexer.process_batch(articles, chunks, ["1", "2"], FakeEmbedder(), q_mgr, conn, use_sparse=True)  # type: ignore[arg-type]
    finally:
        indexer.QDRANT_UPSERT_BATCH_SIZE = original_batch

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM legal_articles")
    article_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM legal_chunks")
    chunk_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM indexing_status")
    status_count = cursor.fetchone()[0]
    cursor.execute("SELECT doc_id FROM indexing_status ORDER BY doc_id")
    status_rows = [row[0] for row in cursor.fetchall()]
    print("COUNTS:", article_count, chunk_count)
    print("INDEXING_STATUS:", status_count, status_rows)
    assert article_count == 2
    assert chunk_count == 2
    assert status_count == 2
    assert len(q_mgr.client.calls) == 2

    conn.close()
    os.remove(db_path)
    if original_sqlite_path is None:
        os.environ.pop("SQLITE_DB_PATH", None)
    else:
        os.environ["SQLITE_DB_PATH"] = original_sqlite_path


if __name__ == "__main__":
    check_tree_helpers()
    asyncio.run(check_process_batch())
    print("HARNESS_OK")






