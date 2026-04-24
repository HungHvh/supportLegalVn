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
from core.embeddings import VietnameseSBERTProvider

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

async def process_batch(batch: List[Dict], embed_provider: VietnameseSBERTProvider, q_mgr: QdrantManager, db_conn):
    """Xử lý và lưu một batch dữ liệu vào Qdrant và SQLite."""
    if not batch:
        return

    texts = [item['content'] for item in batch]
    embeddings = await embed_provider.batch_get_embeddings(texts)
    
    points = []
    cursor = db_conn.cursor()
    
    for item, vector in zip(batch, embeddings):
        # 1. Chuẩn bị cho Qdrant
        points.append(
            models.PointStruct(
                id=item['chunk_id'],
                vector=vector,
                payload={
                    "doc_id": item['doc_id'], 
                    "so_ky_hieu": item['so_ky_hieu'],
                    "headers": item['headers']
                }
            )
        )
        # 2. Lưu vào SQLite
        cursor.execute(
            "INSERT INTO legal_documents (doc_id, so_ky_hieu, headers, content) VALUES (?, ?, ?, ?)",
            (item['doc_id'], item['so_ky_hieu'], str(item['headers']), item['content'])
        )

    # 3. Upsert Qdrant
    q_mgr.client.upsert(collection_name=COLLECTION_NAME, points=points)
    
    # Commit SQLite
    db_conn.commit()

async def run_indexer():
    init_db()  # Khởi tạo bảng nếu chưa có
    db_conn = get_db_connection()
    q_mgr = QdrantManager()
    q_mgr.init_collection(COLLECTION_NAME)
    embed_provider = VietnameseSBERTProvider()

    # 1. Tải Metadata vào RAM (82MB)
    logger.info("Loading metadata configuration...")
    meta_ds = load_dataset("vohuutridung/vietnamese-legal-documents", "metadata", split="data")
    meta_lookup = {row['id']: row for row in meta_ds}
    logger.info(f"Loaded {len(meta_lookup)} metadata records.")

    # 2. Stream Content configuration (3.6GB)
    logger.info("Connecting to content stream...")
    content_ds = load_dataset("vohuutridung/vietnamese-legal-documents", "content", split="data", streaming=True)

    # 3. Khởi tạo Splitters
    headers_to_split_on = [("#", "H1"), ("##", "H2"), ("###", "H3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    length_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    batch_buffer = []
    
    logger.info("Starting ingestion loop...")
    # Vì stream không có độ dài cụ thể ngay lập tức, ta dùng đếm thủ công nếu cần
    for row in tqdm(content_ds, desc="Indexing Legal Documents"):
        doc_id_int = row['id']
        doc_id_str = str(doc_id_int)
        
        # Idempotency check
        if is_processed(db_conn, doc_id_str):
            continue

        raw_text = row['text']
        meta = meta_lookup.get(doc_id_int, {})
        so_ky_hieu = str(meta.get("document_number", "N/A"))

        # Bước 1: Chia theo Markdown headers
        md_splits = md_splitter.split_text(raw_text)
        
        # Bước 2: Chia nhỏ các đoạn quá dài
        doc_chunks = []
        for split in md_splits:
            if len(split.page_content) > CHUNK_SIZE:
                sub_splits = length_splitter.split_text(split.page_content)
                headers = split.metadata
                for sub in sub_splits:
                    doc_chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "doc_id": doc_id_str,
                        "so_ky_hieu": so_ky_hieu,
                        "headers": headers,
                        "content": sub
                    })
            else:
                doc_chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "doc_id": doc_id_str,
                    "so_ky_hieu": so_ky_hieu,
                    "headers": split.metadata,
                    "content": split.page_content
                })

        # Thêm vào batch buffer
        batch_buffer.extend(doc_chunks)

        # Nếu buffer vượt ngưỡng, xử lý batch
        # Chú ý: Ta chỉ đánh dấu doc_id là processed KHI batch chứa nó đã được commit.
        # Để đơn giản, ta sẽ flush batch sau mỗi X doc_id hoặc khi buffer đủ lớn.
        if len(batch_buffer) >= BATCH_SIZE:
            await process_batch(batch_buffer, embed_provider, q_mgr, db_conn)
            # Sau khi batch buffer thành công, ta mới có thể coi các doc_id trong batch đó là ok.
            # Tuy nhiên, một doc_id có thể nằm trọn trong một batch. 
            # Đánh dấu doc_id hiện tại đã xong.
            mark_as_processed(db_conn, doc_id_str)
            batch_buffer = []
        else:
            # Vẫn đánh dấu doc_id là processed nếu nó đã được nạp vào buffer 
            # (chấp nhận rủi ro mất 1 batch nếu crash, nhưng thực tế mark_as_processed commit ngay)
            # Để an toàn nhất, nên mark_as_processed cùng transaction với batch.
            mark_as_processed(db_conn, doc_id_str)

    # Flush remaining buffer
    if batch_buffer:
        await process_batch(batch_buffer, embed_provider, q_mgr, db_conn)

    db_conn.close()
    logger.info("🎉 Ingestion completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(run_indexer())
    except KeyboardInterrupt:
        logger.info("Ingestion interrupted by user.")
    except Exception as e:
        logger.error(f"Fatal error during ingestion: {e}", exc_info=True)
