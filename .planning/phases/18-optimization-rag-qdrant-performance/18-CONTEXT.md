# Phase 18: Tối ưu RAG & Qdrant - Hiệu năng - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary
Phase này tập trung vào việc tối ưu hóa hiệu năng của hệ thống RAG và kết nối Qdrant, bao gồm triển khai Semantic Cache, chuyển sang gRPC, và áp dụng Pre-filtering.
</domain>

<decisions>
## Implementation Decisions

### 1. Semantic Cache (Qdrant-based)
- **Công nghệ**: Sử dụng chính Qdrant làm Cache thay vì cài thêm Redis.
- **Collection**: Tạo collection mới tên là `semantic_cache`.
- **Logic**: 
    - `check_semantic_cache`: Tìm kiếm vector với `score_threshold=0.95`.
    - Trả về `llm_response` nếu tìm thấy.
    - `save_to_cache`: Lưu `query_text`, `query_vector`, và `llm_response` với UUID ngẫu nhiên.
    - **Timestamp**: Đính kèm `created_at` (timestamp) vào mỗi entry để phục vụ việc dọn dẹp.

### 4. Background Cache Cleanup (TTL)
- **Cơ chế**: Viết một background worker (script) định kỳ dọn dẹp cache.
- **Logic**: Tìm và xóa các points trong `semantic_cache` có `created_at` cũ hơn 30 ngày.
- **Index**: Cần đánh index cho trường `created_at` trong `semantic_cache`.


### 2. gRPC Migration
- **Port**: Chuyển từ 6333 sang 6334.
- **Client**: Sử dụng `prefer_grpc=True` khi khởi tạo `QdrantClient`.
- **Infrastructure**: Cần cập nhật `docker-compose.yml` để map port 6334.(đã có không cần làm gì)

### 3. Payload Pre-filtering
- **Fields**: Index các trường `nam_ban_hanh` (INTEGER) và `linh_vuc` (KEYWORD).
- **Setup**: Tạo payload index một lần duy nhất lúc setup.
- **Search**: Trích xuất metadata từ query (năm, lĩnh vực) và đưa vào `models.Filter`.

</decisions>

<canonical_refs>
## Canonical References
- `db/qdrant.py` — Quản lý client và khởi tạo collection.
- `retrievers/qdrant_retriever.py` — Logic tìm kiếm vector.
- `core/rag_pipeline.py` — Pipeline RAG chính.
- `docker-compose.yml` — Cấu hình container.
</canonical_refs>

<specifics>
## Specific Ideas
- Sử dụng UUID ngẫu nhiên cho ID của cache points.
- Metadata `year` có thể trích xuất bằng regex hoặc LLM classifier.
</specifics>

<deferred>
## Deferred Ideas
- (None)

</deferred>

---
*Phase: 18-optimization-rag-qdrant-performance*
*Context gathered: 2026-05-05*
