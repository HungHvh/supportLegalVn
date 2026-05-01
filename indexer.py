import os
import time
import uuid
import logging
import asyncio
from time import monotonic
from tqdm import tqdm

from datasets import load_dataset
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.http import models
from dotenv import load_dotenv

from db.sqlite import get_db_connection, init_db
from db.qdrant import QdrantManager
from core.embeddings import VietnameseSBERTProvider, HybridEmbeddingProvider
from core.parser import VietnameseLegalParser, LegalNode, LegalLevel

# ===== ENV =====
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_EMBED_CHARS = int(os.getenv("MAX_EMBED_CHARS", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 30))
QDRANT_BATCH = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", 256))

# 🔥 NEW
MAX_ARTICLES_PER_FLUSH = int(os.getenv("MAX_ARTICLES_PER_FLUSH", 1000))
INDEX_CHUNKS = os.getenv("INDEX_CHUNKS", "0") == "1"

COLLECTION_ARTICLE = "legal_articles"
COLLECTION_CHUNK = "legal_chunks"

# ===== SPLITTER =====
splitter = RecursiveCharacterTextSplitter(
    chunk_size=MAX_EMBED_CHARS,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""]
)

# ===== WAIT QDRANT =====
async def wait_qdrant():
    deadline = monotonic() + 120
    while monotonic() < deadline:
        try:
            q = QdrantManager()
            q.client.get_collections()
            return
        except Exception:
            await asyncio.sleep(2)
    raise RuntimeError("Qdrant not ready")

# ===== FLATTEN =====
def flatten(node: LegalNode):
    parts = []
    stack = [node]
    while stack:
        n = stack.pop()
        if n.title:
            parts.append(n.title)
        if n.content:
            t = n.content.strip()
            if t:
                parts.append(t)
        stack.extend(reversed(n.children))
    return "\n".join(parts)

# ===== SPLIT =====
def split_article(node: LegalNode, full_text: str):
    return [
        {
            "path": node.full_path,
            "text": sub,
            "level": "ARTICLE"
        }
        for sub in splitter.split_text(full_text)
    ]

# ===== COLLECT =====
def collect(root, doc_id, so_ky_hieu):
    articles, chunks = [], []

    stack = [root]
    article_nodes = []

    while stack:
        n = stack.pop()
        if n.level == LegalLevel.ARTICLE:
            article_nodes.append(n)
        stack.extend(n.children)

    for node in article_nodes:
        aid = str(uuid.uuid4())
        full = flatten(node)

        articles.append({
            "article_uuid": aid,
            "doc_id": doc_id,
            "so_ky_hieu": so_ky_hieu,
            "article_title": node.title or so_ky_hieu,
            "article_path": node.full_path,
            "full_content": full
        })

        if INDEX_CHUNKS:
            for c in split_article(node, full):
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "article_uuid": aid,
                    "doc_id": doc_id,
                    "so_ky_hieu": so_ky_hieu,
                    "level": c["level"],
                    "chunk_path": c["path"],
                    "content": c["text"],
                    "enriched_text": f"[{c['path']}] {c['text']}",
                    "article_title": node.title or so_ky_hieu
                })

    return articles, chunks

# ===== EMBEDDING =====
EMBED_BATCH = 64

async def embed_all(texts, embed):
    all_vecs = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        if not batch:
            continue
        # đoạn này gọi GPU nên async không có tác dụng gì
        vecs = await embed.dense.batch_get_embeddings(batch)
        all_vecs.extend(vecs)
    return all_vecs

# ===== PROCESS =====
async def process_batch(articles, chunks, doc_ids, embed, q_mgr, db):

    if not articles:
        return

    # ===== EMBED ARTICLES =====
    article_texts = [
        f"{a['article_title']}\n{a['full_content']}"
        for a in articles
    ]

    vecs = await embed_all(article_texts, embed)

    cur = db.cursor()

    # ===== SQLITE =====
    cur.executemany(
        """INSERT OR IGNORE INTO legal_articles
        (article_uuid, doc_id, so_ky_hieu, article_title, article_path, full_content)
        VALUES (?,?,?,?,?,?)""",
        [(a["article_uuid"], a["doc_id"], a["so_ky_hieu"], a["article_title"], a["article_path"], a["full_content"]) for a in articles]
    )

    # ===== QDRANT ARTICLE =====
    points = [
        models.PointStruct(
            id=a["article_uuid"],
            vector={"dense": v},
            payload={
                "article_uuid": a["article_uuid"],
                "doc_id": a["doc_id"],
                "so_ky_hieu": a["so_ky_hieu"],
                "article_title": a["article_title"],
                "full_content": a["full_content"]
            }
        )
        for a, v in zip(articles, vecs)
    ]

    q_mgr.client.upsert(
        collection_name=COLLECTION_ARTICLE,
        points=points,
        wait=False
    )

    # ===== OPTIONAL CHUNK =====
    if INDEX_CHUNKS and chunks:
        cur.executemany(
            """INSERT OR IGNORE INTO legal_chunks
            (chunk_id, article_uuid, doc_id, so_ky_hieu, level, chunk_path, content)
            VALUES (?,?,?,?,?,?,?)""",
            [(c["chunk_id"], c["article_uuid"], c["doc_id"], c["so_ky_hieu"], c["level"], c["chunk_path"], c["content"]) for c in chunks]
        )

    db.commit()

    print(f"✔ batch ok: {len(doc_ids)} docs, {len(articles)} articles")

# ===== MAIN =====
async def run():

    await wait_qdrant()
    init_db()

    db = get_db_connection()

    embed = HybridEmbeddingProvider(VietnameseSBERTProvider())
    q_mgr = QdrantManager()

    q_mgr.init_collection(COLLECTION_ARTICLE)
    if INDEX_CHUNKS:
        q_mgr.init_collection(COLLECTION_CHUNK)

    parser = VietnameseLegalParser()

    meta = load_dataset("vohuutridung/vietnamese-legal-documents", "metadata", split="data")
    meta_map = {m["id"]: m for m in meta}

    content = load_dataset("vohuutridung/vietnamese-legal-documents", "content", split="data")

    pending = []

    for row in tqdm(content):

        doc_id = str(row["id"])

        so = str(meta_map.get(row["id"], {}).get("document_number", "N/A"))

        root = parser.parse_document(row["content"], law_name=so)
        articles, chunks = collect(root, doc_id, so)

        pending.append({
            "doc_id": doc_id,
            "articles": articles,
            "chunks": chunks
        })

        # ✅ FIX: chỉ tính article
        total_articles = sum(len(d["articles"]) for d in pending)

        if total_articles >= MAX_ARTICLES_PER_FLUSH:
            print("flush batch:", len(pending), "docs,", total_articles, "articles")
            await flush(pending, embed, q_mgr, db)

    await flush(pending, embed, q_mgr, db)

# ===== FLUSH =====
async def flush(pending, embed, q_mgr, db):

    if not pending:
        return

    articles, chunks, ids = [], [], []

    for d in pending:
        articles.extend(d["articles"])
        chunks.extend(d["chunks"])
        ids.append(d["doc_id"])

    await process_batch(articles, chunks, ids, embed, q_mgr, db)

    pending.clear()

# ===== ENTRY =====
if __name__ == "__main__":
    asyncio.run(run())