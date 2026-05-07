import sqlite3
import uuid
import pandas as pd
from datasets import load_dataset
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_text_splitters import MarkdownHeaderTextSplitter

from core.embeddings import VietnameseSBERTProvider

# ==========================================
# 1. KHỞI TẠO CƠ SỞ DỮ LIỆU & MODEL
# ==========================================
print("1. Đang khởi tạo Database và Model...")

# Khởi tạo SQLite (Lưu file text và FTS5)
db_conn = sqlite3.connect("sqlite_data/legal_poc.db")
cursor = db_conn.cursor()

# Xóa bảng cũ nếu chạy lại script
cursor.execute("DROP TABLE IF EXISTS chunks_metadata;")
cursor.execute("DROP TABLE IF EXISTS chunks_fts;")

# Bảng lưu metadata gốc
cursor.execute("""
CREATE TABLE chunks_metadata (
    id TEXT PRIMARY KEY,
    so_ky_hieu TEXT,
    headers TEXT,
    content TEXT
);
""")
# Bảng FTS5 để search Text tốc độ cao (BM25-like)
cursor.execute("""
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    id UNINDEXED, 
    content, 
    so_ky_hieu
);
""")
db_conn.commit()

# Khởi tạo Qdrant (Chạy trực tiếp trên RAM)
q_client = QdrantClient(":memory:")

# Khởi tạo Embedding Model an toàn với fallback safetensors-compatible
dense_provider = VietnameseSBERTProvider()
embedding_model = dense_provider.model
embedding_dimension = dense_provider.dimension

# Kiểm tra và tạo collection (Thay thế recreate_collection đã bị remove/deprecated)
if q_client.collection_exists(collection_name="legal_vectors"):
    q_client.delete_collection(collection_name="legal_vectors")

q_client.create_collection(
    collection_name="legal_vectors",
    vectors_config=models.VectorParams(size=embedding_dimension, distance=models.Distance.COSINE),
)

# ==========================================
# 2. TẢI VÀ XỬ LÝ DỮ LIỆU (DATA INGESTION)
# ==========================================
print("\n2. Đang tải dữ liệu từ Hugging Face (lấy 50 văn bản đầu tiên để test)...")
# Dùng streaming=True để không phải tải toàn bộ 3.6GB về máy
dataset = load_dataset("vohuutridung/vietnamese-legal-documents", "content", split="data", streaming=True)
meta_dataset = load_dataset("vohuutridung/vietnamese-legal-documents", "metadata", split="data", streaming=True)

# Lấy 50 văn bản làm mẫu
sample_content = list(dataset.take(50))
sample_meta = list(meta_dataset.take(50))

# Ghép content và metadata
df_content = pd.DataFrame(sample_content)
df_meta = pd.DataFrame(sample_meta)
df = df_meta.merge(df_content, on="id")

print(f"Đã tải {len(df)} văn bản. Đang tiến hành Chunking và Vector hóa...")

# Cấu hình chia Markdown
headers_to_split_on = [("#", "Header_1"), ("##", "Header_2"), ("###", "Header_3")]
markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

qdrant_points = []

for index, row in df.iterrows():
    text_content = row['content']
    so_ky_hieu = str(row['document_number'])

    # Cắt thành các chunk nhỏ (ví dụ: từng Điều)
    splits = markdown_splitter.split_text(text_content)

    for chunk in splits:
        chunk_id = str(uuid.uuid4())
        content_text = chunk.page_content
        headers_str = str(chunk.metadata)  # Lưu lại cấu trúc Header

        # 1. Lưu vào SQLite
        cursor.execute("INSERT INTO chunks_metadata VALUES (?, ?, ?, ?)",
                       (chunk_id, so_ky_hieu, headers_str, content_text))
        cursor.execute("INSERT INTO chunks_fts (id, content, so_ky_hieu) VALUES (?, ?, ?)",
                       (chunk_id, content_text, so_ky_hieu))

        # 2. Tạo Vector
        vector = embedding_model.encode(content_text).tolist()

        # 3. Chuẩn bị point cho Qdrant
        qdrant_points.append(
            models.PointStruct(
                id=chunk_id,
                vector=vector,
                payload={"so_ky_hieu": so_ky_hieu}  # Có thể filter theo số hiệu nếu cần
            )
        )

db_conn.commit()

# Insert hàng loạt vào Qdrant
q_client.upsert(collection_name="legal_vectors", points=qdrant_points)
print(f"Đã nhúng thành công {len(qdrant_points)} chunks vào Database!")


# ==========================================
# 3. HÀM TRUY VẤN HYBRID (RETRIEVAL)
# ==========================================
def hybrid_search(query: str, top_k: int = 3):
    # --- A. SEMANTIC SEARCH (Qdrant) ---
    query_vector = embedding_model.encode(query).tolist()
    # Sử dụng query_points thay thế cho search() trong các version qdrant-client mới
    search_result = q_client.query_points(
        collection_name="legal_vectors",
        query=query_vector,
        limit=10  # Lấy dư ra để tính toán RRF
    )
    semantic_results = search_result.points

    # --- B. KEYWORD SEARCH (SQLite FTS5) ---
    # Chuẩn hóa query bỏ ký tự đặc biệt để tránh lỗi SQLite
    safe_query = query.replace('"', '').replace("'", "")
    fts_query = f"""
        SELECT id, bm25(chunks_fts) as score 
        FROM chunks_fts 
        WHERE chunks_fts MATCH '"{safe_query}"' 
        ORDER BY score ASC LIMIT 10
    """  # bm25 trong SQLite trả số âm, càng nhỏ càng tốt

    cursor.execute(fts_query)
    keyword_results = cursor.fetchall()

    # --- C. GỘP KẾT QUẢ BẰNG RECIPROCAL RANK FUSION (RRF) ---
    RRF_K = 60  # Hằng số làm mượt
    scores = {}

    # Tính điểm RRF cho Vector search
    for rank, hit in enumerate(semantic_results):
        scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (RRF_K + rank + 1)

    # Tính điểm RRF cho Keyword search
    for rank, (doc_id, _) in enumerate(keyword_results):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)

    # Sắp xếp lại dựa trên điểm RRF
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]

    # Lấy text thực tế từ Database để in ra
    final_results = []
    for doc_id in sorted_ids:
        cursor.execute("SELECT so_ky_hieu, headers, content FROM chunks_metadata WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if row:
            final_results.append({
                "so_ky_hieu": row[0],
                "headers": row[1],
                "content": row[2][:250] + "..."  # Cắt ngắn để dễ nhìn
            })

    return final_results


# ==========================================
# 4. CHẠY THỬ NGHIỆM
# ==========================================
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("HỆ THỐNG TRUY VẤN VĂN BẢN PHÁP LUẬT (HYBRID SEARCH)")
    print("=" * 50)
    print("Gõ 'exit' hoặc 'quit' để thoát.")

    while True:
        try:
            query = input("\n[Câu hỏi của bạn]: ").strip()
            
            if not query:
                continue
                
            if query.lower() in ["exit", "quit", "thoát"]:
                print("Đang thoát hệ thống...")
                break
            
            print(f"Đang tìm kiếm...")
            results = hybrid_search(query)
            
            if not results:
                print("-> Không tìm thấy kết quả phù hợp trong dữ liệu mẫu.")
            else:
                for i, res in enumerate(results):
                    print(f"\n  + Top {i + 1} | Số hiệu: {res['so_ky_hieu']}")
                    print(f"    Cấu trúc: {res['headers']}")
                    print(f"    Trích dẫn: {res['content']}")
                    print("-" * 40)
                    
        except KeyboardInterrupt:
            print("\nĐã ngắt bởi người dùng.")
            break
        except Exception as e:
            print(f"Có lỗi xảy ra: {e}")
