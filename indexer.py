import os
import time
import uuid
import logging
import asyncio
from time import monotonic
from tqdm import tqdm
from typing import Any, List, Dict, Tuple

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

BATCH_SIZE = int(os.getenv("BATCH_SIZE", 512))
DOCS_PER_COMMIT = 50 # int(os.getenv("DOCS_PER_COMMIT", 200))
MAX_EMBED_CHARS = int(os.getenv("MAX_EMBED_CHARS", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))
QDRANT_BATCH = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", 256))
MAX_CHUNKS_PER_BATCH = 800

COLLECTION_NAME = "legal_chunks"

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
    chunks = []
    for sub in splitter.split_text(full_text):
        chunks.append({
            "path": node.full_path,
            "text": sub,
            "level": "ARTICLE"
        })
    return chunks

# ===== COLLECT =====
def collect(root, doc_id, so_ky_hieu):
    articles, chunks = [], []

    stack = [root]
    articles_nodes = []

    while stack:
        n = stack.pop()
        if n.level == LegalLevel.ARTICLE:
            articles_nodes.append(n)
        stack.extend(n.children)

    for node in articles_nodes:
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

        for c in split_article(node, full):
            cid = str(uuid.uuid4())
            chunks.append({
                "chunk_id": cid,
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

# ===== LOAD PROCESSED =====
def load_ids(db):
    cur = db.cursor()
    cur.execute("SELECT doc_id FROM indexing_status")
    return {r[0] for r in cur.fetchall()}


# IMPROVE MULTI-THREADING/ASYNC EMBEDDING
EMBED_BATCH = 32          # 16–64 tùy RAM/GPU
EMBED_CONCURRENCY = 4     # 2–8 tùy CPU/GPU

sem = asyncio.Semaphore(EMBED_CONCURRENCY)


async def embed_sub(texts, embed):
    async with sem:
        return await embed.dense.batch_get_embeddings(texts)

async def embed_all(texts, embed):
    tasks = [
        asyncio.create_task(embed_sub(texts[i:i + EMBED_BATCH], embed))
        for i in range(0, len(texts), EMBED_BATCH)
    ]
    batches = await asyncio.gather(*tasks)
    return [vec for batch in batches for vec in batch]

# ===== PROCESS =====
async def process_batch(articles, chunks, doc_ids, embed, q_mgr, db):
    if not chunks:
        return

    # 🔥 FIX: giữ mapping 1-1
    pairs = [(c, c["enriched_text"]) for c in chunks if c["enriched_text"].strip()]

    if not pairs:
        return

    valid_chunks, texts = zip(*pairs)

    try:
        # VERY SLOW
        vecs = await embed_all(list(texts), embed)
    except Exception as e:
        logger.error(f"Embedding error: {e}", exc_info=True)
        raise

    if len(vecs) != len(valid_chunks):
        raise RuntimeError("Embedding mismatch")

    cur = db.cursor()

    # insert articles
    cur.executemany(
        """INSERT OR IGNORE INTO legal_articles
        (article_uuid, doc_id, so_ky_hieu, article_title, article_path, full_content)
        VALUES (?,?,?,?,?,?)""",
        [(a["article_uuid"], a["doc_id"], a["so_ky_hieu"], a["article_title"], a["article_path"], a["full_content"]) for a in articles]
    )

    # batch insert
    for i in range(0, len(valid_chunks), QDRANT_BATCH):

        sub_chunks = valid_chunks[i:i+QDRANT_BATCH]
        sub_vecs = vecs[i:i+QDRANT_BATCH]

        cur.executemany(
            """INSERT OR IGNORE INTO legal_chunks
            (chunk_id, article_uuid, doc_id, so_ky_hieu, level, chunk_path, content)
            VALUES (?,?,?,?,?,?,?)""",
            [(c["chunk_id"], c["article_uuid"], c["doc_id"], c["so_ky_hieu"], c["level"], c["chunk_path"], c["content"]) for c in sub_chunks]
        )

        points = [
            models.PointStruct(
                id=c["chunk_id"],
                # vector={"dense": v["dense"], "sparse": v.get("sparse", [])},
                vector={"dense": v},
                payload={
                    "chunk_id": c["chunk_id"],
                    "article_uuid": c["article_uuid"],
                    "doc_id": c["doc_id"],
                    "so_ky_hieu": c["so_ky_hieu"],
                    "level": c["level"],
                    "article_title": c["article_title"]
                }
            )
            for c, v in zip(sub_chunks, sub_vecs)
        ]

        q_mgr.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=False  # 🚀 FIX tốc độ
        )

    cur.executemany(
        "INSERT OR IGNORE INTO indexing_status (doc_id) VALUES (?)",
        [(d,) for d in doc_ids]
    )

    db.commit()
    print(f"✔ batch ok: {len(doc_ids)} docs, {len(valid_chunks)} chunks")
    logger.info(f"✔ batch ok: {len(doc_ids)} docs, {len(valid_chunks)} chunks")

# ===== MAIN =====
async def run():

    await wait_qdrant()
    init_db()

    db = get_db_connection()
    processed = load_ids(db)
    print("DB path:", db)

    embed = HybridEmbeddingProvider(VietnameseSBERTProvider())
    q_mgr = QdrantManager()
    q_mgr.init_collection(COLLECTION_NAME)

    parser = VietnameseLegalParser()

    meta = load_dataset("vohuutridung/vietnamese-legal-documents", "metadata", split="data")
    meta_map = {m["id"]: m for m in meta}

    content = load_dataset("vohuutridung/vietnamese-legal-documents", "content", split="data")

    pending = []

    for row in tqdm(content):

        doc_id = str(row["id"])
        if doc_id in processed:
            continue

        so = str(meta_map.get(row["id"], {}).get("document_number", "N/A"))

        root = parser.parse_document(row["content"], law_name=so)
        articles, chunks = collect(root, doc_id, so)

        pending.append({
            "doc_id": doc_id,
            "articles": articles,
            "chunks": chunks
        })
        total_chunks = sum(len(d["chunks"]) for d in pending)

        if total_chunks >= MAX_CHUNKS_PER_BATCH:
            print("flush batch: pending docs =", len(pending), "total chunks =", total_chunks)
            start_time = time.time()
            await flush(pending, embed, q_mgr, db, processed)
            end_time = time.time()
            print(f"batch flush time: {end_time - start_time:.2f} seconds")

    await flush(pending, embed, q_mgr, db, processed)

# ===== FLUSH =====
async def flush(pending, embed, q_mgr, db, processed):

    if not pending:
        return

    articles, chunks, ids = [], [], []

    for d in pending:
        articles.extend(d["articles"])
        chunks.extend(d["chunks"])
        ids.append(d["doc_id"])

    try:
        await process_batch(articles, chunks, ids, embed, q_mgr, db)
        processed.update(ids)
    except Exception as e:
        logger.error(f"FATAL batch fail: {e}", exc_info=True)
        raise

    pending.clear()

# ===== ENTRY =====
if __name__ == "__main__":
    asyncio.run(run())