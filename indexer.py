import os
import uuid
import logging
import asyncio
from time import monotonic
from tqdm import tqdm
from typing import Any, List, Dict, Tuple
from datasets import load_dataset, DownloadConfig
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.http import models
from dotenv import load_dotenv

from db.sqlite import get_db_connection, init_db
from db.qdrant import QdrantManager
from core.embeddings import VietnameseSBERTProvider, HybridEmbeddingProvider
from core.parser import VietnameseLegalParser, LegalNode, LegalLevel

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config Phase 10
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 512))
MIN_CHUNK_CHARS = int(os.getenv("MIN_CHUNK_CHARS", 50))
MAX_EMBED_CHARS = int(os.getenv("MAX_EMBED_CHARS", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))
MAX_CHUNKS_PER_ARTICLE = int(os.getenv("MAX_CHUNKS_PER_ARTICLE", 20))
DB_COMMIT_INTERVAL = int(os.getenv("DB_COMMIT_INTERVAL", 500))
DOCS_PER_COMMIT = int(os.getenv("DOCS_PER_COMMIT", DB_COMMIT_INTERVAL))
QDRANT_UPSERT_BATCH_SIZE = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", BATCH_SIZE))
COLLECTION_NAME = "legal_chunks"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_WAIT_SECONDS = int(os.getenv("QDRANT_WAIT_SECONDS", 180))
USE_SPARSE_EMBEDDING = os.getenv("USE_SPARSE_EMBEDDING", "true").lower() == "true"

# Initialize Splitter for fallback
recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=MAX_EMBED_CHARS,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""]
)

async def wait_for_qdrant(host: str = QDRANT_HOST, port: int = QDRANT_PORT, timeout: int = QDRANT_WAIT_SECONDS):
    """Block until Qdrant is reachable."""
    deadline = monotonic() + timeout
    last_error = None

    while monotonic() < deadline:
        probe = None
        try:
            probe = QdrantManager(host=host, port=port)
            probe.client.get_collections()
            probe.client.close()
            return
        except Exception as e:
            last_error = e
            logger.info(f"Waiting for Qdrant at {host}:{port}... ({e})")
            if probe is not None:
                try:
                    probe.client.close()
                except Exception:
                    pass
            await asyncio.sleep(3)

    raise TimeoutError(f"Qdrant not ready at {host}:{port} after {timeout}s: {last_error}")

def flatten_article_content(node: LegalNode) -> str:
    """Iteratively concat toàn bộ text của Điều và các Khoản/Điểm con."""
    parts = []
    stack = [(node, False)]

    while stack:
        current, include_title = stack.pop()
        if include_title and current.title:
            parts.append(current.title)
        if current.content and current.content.strip():
            parts.append(current.content.strip())
        for child in reversed(current.children):
            stack.append((child, True))

    return "\n".join(p for p in parts if p)

def split_article(article_node: LegalNode, full_content: str | None = None) -> List[Dict]:
    """
    Hybrid split: structural Khoản boundaries first,
    RecursiveCharacterTextSplitter as fallback for long clauses.
    Short clauses (< MIN_CHUNK_CHARS) merge into parent buffer.
    """
    result_chunks: List[Dict] = []
    parent_buffer: str = ""

    for clause in article_node.children:
        text = clause.content.strip() if clause.content else ""

        # Short clause -> accumulate in buffer
        if len(text) < MIN_CHUNK_CHARS:
            parent_buffer += " " + text
            continue

        # Flush buffer into current clause
        if parent_buffer:
            text = parent_buffer.strip() + " " + text
            parent_buffer = ""

        # Long clause -> split further
        if len(text) > MAX_EMBED_CHARS:
            sub_texts = recursive_splitter.split_text(text)
        else:
            sub_texts = [text]

        for sub in sub_texts:
            result_chunks.append({
                "path": clause.full_path,
                "text": sub,
                "level": clause.level.name if clause.level else "KHOẢN",
            })

    # ⚠️ POST-LOOP FLUSH: flush remaining buffer (Correction #7)
    if parent_buffer:
        result_chunks.append({
            "path": article_node.full_path,
            "text": parent_buffer.strip(),
            "level": "KHOẢN",
        })

    # Fallback: no clause children -> split full_content directly
    if not result_chunks:
        text_to_split = full_content if full_content is not None else flatten_article_content(article_node)
        for sub in recursive_splitter.split_text(text_to_split):
            result_chunks.append({
                "path": article_node.full_path,
                "text": sub,
                "level": "ARTICLE",
            })

    # Soft cap logging
    if len(result_chunks) > MAX_CHUNKS_PER_ARTICLE:
        logger.warning(f"Article {article_node.full_path} produced {len(result_chunks)} chunks (soft cap={MAX_CHUNKS_PER_ARTICLE})")

    return result_chunks

def collect_article_chunks(root: LegalNode, doc_id: str, so_ky_hieu: str) -> Tuple[List[Dict], List[Dict]]:
    """Collect articles and chunks from the parsed tree."""
    articles_batch = []
    chunks_batch = []

    # Find all ARTICLE nodes
    def find_articles(node: LegalNode):
        stack = [node]
        results = []

        while stack:
            current = stack.pop()
            if current.level == LegalLevel.ARTICLE:
                results.append(current)
                continue
            stack.extend(reversed(current.children))

        return results

    article_nodes = find_articles(root)

    for article_node in article_nodes:
        article_uuid = str(uuid.uuid4())
        full_content = flatten_article_content(article_node)
        article_title = article_node.title or so_ky_hieu

        articles_batch.append({
            "article_uuid": article_uuid,
            "doc_id": doc_id,
            "so_ky_hieu": so_ky_hieu,
            "article_title": article_title,
            "article_path": article_node.full_path,
            "full_content": full_content,
        })

        raw_chunks = split_article(article_node, full_content=full_content)
        for c in raw_chunks:
            chunk_id = str(uuid.uuid4())
            # Enrichment: [Breadcrumb] Text
            enriched = f"[{c['path']}] {c['text']}"
            chunks_batch.append({
                "chunk_id": chunk_id,
                "article_uuid": article_uuid,
                "doc_id": doc_id,
                "so_ky_hieu": so_ky_hieu,
                "level": c["level"],
                "chunk_path": c["path"],
                "content": c["text"],
                "enriched_text": enriched,
                "article_title": article_title,
            })

    # Fallback: document has no ARTICLE nodes
    if not article_nodes:
        article_uuid = str(uuid.uuid4())
        raw_text = flatten_article_content(root)
        articles_batch.append({
            "article_uuid": article_uuid,
            "doc_id": doc_id,
            "so_ky_hieu": so_ky_hieu,
            "article_title": so_ky_hieu,
            "article_path": so_ky_hieu,
            "full_content": raw_text,
        })
        for sub in recursive_splitter.split_text(raw_text):
            chunk_id = str(uuid.uuid4())
            chunks_batch.append({
                "chunk_id": chunk_id,
                "article_uuid": article_uuid,
                "doc_id": doc_id,
                "so_ky_hieu": so_ky_hieu,
                "level": "ARTICLE",
                "chunk_path": so_ky_hieu,
                "content": sub,
                "enriched_text": f"[{so_ky_hieu}] {sub}",
                "article_title": so_ky_hieu,
            })

    return articles_batch, chunks_batch

def load_processed_ids(db_conn) -> set[str]:
    """Load processed doc_ids once to avoid per-document SQLite lookups."""
    cursor = db_conn.cursor()
    cursor.execute("SELECT doc_id FROM indexing_status")
    return {row[0] for row in cursor.fetchall()}

async def process_batch(articles: List[Dict], chunks: List[Dict], doc_ids: List[str], embed_provider: Any, q_mgr: QdrantManager, db_conn, use_sparse: bool = True):
    """Process and save a batch to Qdrant and SQLite."""
    if not chunks:
        return

    try:
        # Embed only chunks
        texts_for_embedding = [
            c.get("enriched_text")
            or f"[{c.get('chunk_path') or c.get('path') or c.get('full_path') or ''}] {c.get('content', '')}".strip()
            for c in chunks
        ]
        # remote empty texts to avoid embedding errors
        texts_for_embedding = [t for t in texts_for_embedding if t.strip()]
        
        if use_sparse:
            hybrid_embeddings = await embed_provider.get_hybrid_embeddings(texts_for_embedding)
        else:
            logger.warning("⚠️ Using DENSE ONLY embeddings")
            if hasattr(embed_provider, "dense") and hasattr(embed_provider.dense, "batch_get_embeddings"):
                dense_vectors = await embed_provider.dense.batch_get_embeddings(texts_for_embedding)
            elif hasattr(embed_provider, 'get_dense_embeddings'):
                dense_vectors = await embed_provider.get_dense_embeddings(texts_for_embedding)
            elif hasattr(embed_provider, 'batch_get_embeddings'):
                dense_vectors = await embed_provider.batch_get_embeddings(texts_for_embedding)
            else:
                dense_vectors = await embed_provider.get_hybrid_embeddings(texts_for_embedding)
            hybrid_embeddings = [{"dense": v, "sparse": []} for v in (dense_vectors if isinstance(dense_vectors, list) else [dense_vectors])]

        if len(chunks) != len(hybrid_embeddings):
            raise ValueError(
                f"Embedding count mismatch: {len(chunks)} chunks vs {len(hybrid_embeddings)} vectors"
            )

        cursor = db_conn.cursor()
        
        # Insert articles first
        article_records = [
            (a["article_uuid"], a["doc_id"], a["so_ky_hieu"], a["article_title"], a["article_path"], a["full_content"])
            for a in articles
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO legal_articles (article_uuid, doc_id, so_ky_hieu, article_title, article_path, full_content) VALUES (?,?,?,?,?,?)",
            article_records
        )

        chunk_batch_size = max(1, min(QDRANT_UPSERT_BATCH_SIZE, len(chunks)))
        for start in range(0, len(chunks), chunk_batch_size):
            batch_chunks = chunks[start:start + chunk_batch_size]
            batch_embeddings = hybrid_embeddings[start:start + chunk_batch_size]

            if len(batch_chunks) != len(batch_embeddings):
                raise ValueError(
                    f"Embedding count mismatch in sub-batch: {len(batch_chunks)} chunks vs {len(batch_embeddings)} vectors"
                )

            batch_chunk_records = [
                (c["chunk_id"], c["article_uuid"], c["doc_id"], c["so_ky_hieu"], c["level"], c["chunk_path"], c["content"])
                for c in batch_chunks
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO legal_chunks (chunk_id, article_uuid, doc_id, so_ky_hieu, level, chunk_path, content) VALUES (?,?,?,?,?,?,?)",
                batch_chunk_records
            )

            points = [
                models.PointStruct(
                    id=c["chunk_id"],
                    vector={
                        "dense": vec["dense"],
                        "sparse": vec.get("sparse", [])
                    },
                    payload={
                        "chunk_id": c["chunk_id"],
                        "article_uuid": c["article_uuid"],
                        "doc_id": c["doc_id"],
                        "so_ky_hieu": c["so_ky_hieu"],
                        "level": c["level"],
                        "article_title": c["article_title"],
                    }
                )
                for c, vec in zip(batch_chunks, batch_embeddings)
            ]

            q_mgr.client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)

        # Mark doc_ids as processed
        for d_id in doc_ids:
            cursor.execute("INSERT OR IGNORE INTO indexing_status (doc_id) VALUES (?)", (d_id,))
            
        db_conn.commit()
        logger.info(f"✅ Processed batch: {len(articles)} articles, {len(chunks)} chunks.")
        
    except Exception as e:
        db_conn.rollback()
        logger.error(f"❌ Error processing batch: {e}", exc_info=True)
        raise

async def run_indexer(limit: int = None):
    """Main ingestion loop."""
    await wait_for_qdrant()
    init_db()
    db_conn = get_db_connection()
    dense_provider = VietnameseSBERTProvider()
    q_mgr = QdrantManager()
    q_mgr.init_collection(COLLECTION_NAME, vector_size=dense_provider.dimension)
    embed_provider = HybridEmbeddingProvider(dense_provider)
    parser = VietnameseLegalParser()

    dataset_name = "vohuutridung/vietnamese-legal-documents"
    
    logger.info("Loading datasets...")
    try:
        try:
            meta_ds = load_dataset(dataset_name, "metadata", split="data", download_config=DownloadConfig(local_files_only=True))
        except Exception:
            meta_ds = load_dataset(dataset_name, "metadata", split="data")
        meta_lookup = {row['id']: row for row in meta_ds}
        
        try:
            content_ds = load_dataset(dataset_name, "content", split="data", download_config=DownloadConfig(local_files_only=True))
        except Exception:
            content_ds = load_dataset(dataset_name, "content", split="data")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        return

    pending_docs = []
    processed_ids = load_processed_ids(db_conn)
    processed_count = 0
    
    logger.info(f"Starting ingestion: BATCH_SIZE={BATCH_SIZE}, DOCS_PER_COMMIT={DOCS_PER_COMMIT}, MIN_CHUNK_CHARS={MIN_CHUNK_CHARS}")

    async def flush_pending_docs():
        if not pending_docs:
            return

        batch_articles = []
        batch_chunks = []
        batch_doc_ids = []

        for doc in pending_docs:
            batch_articles.extend(doc["articles"])
            batch_chunks.extend(doc["chunks"])
            batch_doc_ids.append(doc["doc_id"])

        await process_batch(batch_articles, batch_chunks, batch_doc_ids, embed_provider, q_mgr, db_conn, use_sparse=USE_SPARSE_EMBEDDING)
        processed_ids.update(batch_doc_ids)
        pending_docs.clear()
    
    for row in tqdm(content_ds, desc="Indexing Legal Articles"):
        if limit and processed_count >= limit:
            break

        doc_id_int = row['id']
        doc_id_str = str(doc_id_int)
        
        if doc_id_str in processed_ids:
            continue

        raw_text = row['content']
        meta = meta_lookup.get(doc_id_int, {})
        so_ky_hieu = str(meta.get("document_number", "N/A"))

        # Parse and collect
        root_node = parser.parse_document(raw_text, law_name=so_ky_hieu)
        articles, chunks = collect_article_chunks(root_node, doc_id_str, so_ky_hieu)

        processed_count += 1

        pending_docs.append({
            "doc_id": doc_id_str,
            "articles": articles,
            "chunks": chunks,
        })

        if len(pending_docs) >= DOCS_PER_COMMIT or sum(len(d["chunks"]) for d in pending_docs) > MAX_CHUNKS_PER_ARTICLE:
            await flush_pending_docs()

    # Final batch
    await flush_pending_docs()

    db_conn.close()
    logger.info("🎉 Ingestion completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(run_indexer())
    except KeyboardInterrupt:
        logger.info("Ingestion interrupted by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
