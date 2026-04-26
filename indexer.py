import os
import uuid
import logging
import asyncio
from tqdm import tqdm
from typing import List, Dict
from datasets import load_dataset
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from qdrant_client.http import models
from dotenv import load_dotenv

from db.sqlite import get_db_connection, is_processed, mark_as_processed, init_db
from db.qdrant import QdrantManager
from core.embeddings import VietnameseSBERTProvider, HybridEmbeddingProvider
from core.parser import VietnameseLegalParser, LegalNode

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 64))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))
COLLECTION_NAME = "legal_chunks"

async def process_batch(batch: List[Dict], doc_ids: List[str], embed_provider: VietnameseSBERTProvider, q_mgr: QdrantManager, db_conn):
    """
    Process and save a batch of data to Qdrant and SQLite.
    
    Args:
        batch: List of chunk dictionaries.
        doc_ids: List of document IDs being committed in this batch.
        embed_provider: Provider for embeddings.
        q_mgr: Manager for Qdrant operations.
        db_conn: SQLite database connection.
    """
    if not batch:
        return

    try:
        # Get Hybrid Embeddings (Dense + Sparse)
        texts_for_embedding = [item['content_for_embedding'] for item in batch]
        hybrid_embeddings = await embed_provider.get_hybrid_embeddings(texts_for_embedding)
        
        points = []
        cursor = db_conn.cursor()
        
        for item, vectors in zip(batch, hybrid_embeddings):
            # 1. Qdrant point
            points.append(
                models.PointStruct(
                    id=item['chunk_id'],
                    vector={
                        "dense": vectors["dense"],
                        "sparse": vectors["sparse"]
                    },
                    payload={
                        "doc_id": item['doc_id'], 
                        "so_ky_hieu": item['so_ky_hieu'],
                        "full_path": item['full_path'],
                        "level": item['level']
                    }
                )
            )
            # 2. SQLite record
            cursor.execute(
                "INSERT INTO legal_documents (doc_id, so_ky_hieu, full_path, content) VALUES (?, ?, ?, ?)",
                (item['doc_id'], item['so_ky_hieu'], item['full_path'], item['content'])
            )

        # 3. Upsert Qdrant (Retry logic could be added here)
        q_mgr.client.upsert(collection_name=COLLECTION_NAME, points=points)
        
        # 4. Mark all doc_ids in this batch as processed
        for d_id in doc_ids:
            cursor.execute("INSERT OR IGNORE INTO indexing_status (doc_id) VALUES (?)", (d_id,))
            
        # 5. Commit everything atomically
        db_conn.commit()
        logger.info(f"Successfully processed batch of {len(batch)} chunks for {len(doc_ids)} documents.")
        
    except Exception as e:
        db_conn.rollback()
        logger.error(f"Error processing batch: {e}", exc_info=True)
        raise

async def run_indexer(limit: int = None):
    """
    Main ingestion loop.
    
    Args:
        limit: Optional number of documents to process for testing.
    """
    init_db()
    db_conn = get_db_connection()
    q_mgr = QdrantManager()
    q_mgr.init_collection(COLLECTION_NAME)
    dense_provider = VietnameseSBERTProvider()
    embed_provider = HybridEmbeddingProvider(dense_provider)
    parser = VietnameseLegalParser()

    logger.info("Loading metadata configuration...")
    try:
        meta_ds = load_dataset("vohuutridung/vietnamese-legal-documents", "metadata", split="data")
        meta_lookup = {row['id']: row for row in meta_ds}
        logger.info(f"Loaded {len(meta_lookup)} metadata records.")
    except Exception as e:
        logger.error(f"Failed to load metadata: {e}")
        return

    logger.info("Connecting to content stream...")
    content_ds = load_dataset("vohuutridung/vietnamese-legal-documents", "content", split="data", streaming=True)

    headers_to_split_on = [("#", "H1"), ("##", "H2"), ("###", "H3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    length_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    batch_buffer = []
    current_doc_ids = []
    processed_count = 0
    
    logger.info("Starting ingestion loop...")
    for row in tqdm(content_ds, desc="Indexing Legal Documents"):
        if limit and processed_count >= limit:
            break

        doc_id_int = row['id']
        doc_id_str = str(doc_id_int)
        
        if is_processed(db_conn, doc_id_str):
            continue

        raw_text = row['content']
        meta = meta_lookup.get(doc_id_int, {})
        so_ky_hieu = str(meta.get("document_number", "N/A"))

        # Hierarchical Chunking
        root_node = parser.parse_document(raw_text, law_name=so_ky_hieu)
        
        # Flatten the tree into chunks
        doc_chunks = []
        
        def collect_chunks(node: LegalNode):
            # Only index nodes that have content (usually Clause or Point)
            # or Articles if they are short enough.
            if node.content and len(node.content.strip()) > 20:
                # Context Injection: Prefix with breadcrumb
                enriched_text = f"[{node.full_path}] \n {node.content}"
                
                doc_chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "doc_id": doc_id_str,
                    "so_ky_hieu": so_ky_hieu,
                    "full_path": node.full_path,
                    "level": node.level,
                    "content": node.content,
                    "content_for_embedding": enriched_text
                })
            
            for child in node.children:
                collect_chunks(child)

        collect_chunks(root_node)

        batch_buffer.extend(doc_chunks)
        current_doc_ids.append(doc_id_str)
        processed_count += 1

        if len(batch_buffer) >= BATCH_SIZE:
            await process_batch(batch_buffer, current_doc_ids, embed_provider, q_mgr, db_conn)
            batch_buffer = []
            current_doc_ids = []

    if batch_buffer:
        await process_batch(batch_buffer, current_doc_ids, embed_provider, q_mgr, db_conn)

    db_conn.close()
    logger.info("🎉 Ingestion completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(run_indexer())
    except KeyboardInterrupt:
        logger.info("Ingestion interrupted by user.")
    except Exception as e:
        logger.error(f"Fatal error during ingestion: {e}", exc_info=True)
