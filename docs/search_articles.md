# Search Articles API (POST /api/v1/search-articles)

Mục đích: cung cấp endpoint để frontend lấy "nguồn gốc" của câu trả lời RAG — trả về các bản ghi Điều luật canonical (full content) và metadata kèm điểm relevance để hiển thị/đính kèm khi trả lời.

Vị trí endpoint: POST /api/v1/search-articles

Contract (tóm tắt)
- Request (JSON):
  - query: string (tùy chọn) — tìm kiếm theo nội dung/tiêu đề (semantic + BM25)
  - article_uuid: string (tùy chọn) — lấy bài báo canonical theo UUID
  - top_k: int (tùy chọn, mặc định 10)

- Response (200):
  {
    "query": "<query_or_uuid>",
    "top_results_count": <int>,
    "results": [
      {
        "article_uuid": "...",
        "doc_id": "...",
        "so_ky_hieu": "...",
        "title": "...",
        "score": 0.0,
        "full_content": "..."
      },
      ...
    ],
    "status": "success"
  }

Validation / lỗi
- 400: nếu cả `query` và `article_uuid` đều không có.
- 500: lỗi server / DB / retriever exceptions.

Behavior chi tiết
- Nếu `article_uuid` được cung cấp: API gọi `pipeline.retriever.fts_retriever.get_articles_by_uuids([article_uuid])` và trả canonical article (bao gồm `full_content`).
- Nếu `query` được cung cấp: API gọi `pipeline.retriever.aretrieve(query)` (article-first hybrid retriever). Kết quả trả về là article-level nodes (thường đã được hydrated bằng `get_articles_by_uuids` trong pipeline) và được format thành `results`.
- `score` là điểm relevance (float) từ retriever; frontend có thể dùng để sắp/xếp hoặc hiển thị mức độ liên quan.

Frontend usage guidance
- Khi hiển thị nguồn gốc trong giao diện chat, đính kèm `article_uuid`, `so_ky_hieu`, `title` và một đoạn trích (`full_content` hoặc phần tóm tắt). Lưu ý kích thước `full_content` có thể rất dài.
- Đề xuất hiển thị: show first 400–800 chars + nút "Xem toàn bộ" để gọi một endpoint chuyên fetch full_content theo `article_uuid` (nếu frontend muốn).

Performance & safety notes
- Truy vấn trả về `full_content` có thể lớn. Nếu frontend không cần toàn bộ nội dung, sử dụng `retrieve_only` (nội bộ) hoặc sửa pipeline để trả snippet/summary thay vì toàn bộ văn bản.
- Nếu cần giới hạn kích thước trả về, có thể sửa endpoint để trả `snippet_length` hoặc `summary` thay vì `full_content` trực tiếp.

OpenAPI / docs
- Vì endpoint sử dụng Pydantic models (`SearchArticlesRequest`, `SearchArticlesResponse`, `ArticleResult`) nên schema sẽ xuất hiện trong OpenAPI: http://localhost:8000/docs (khi server chạy).

Next steps (trong quy trình GSD)
1. Review tài liệu này với team frontend (discuss). Nếu đồng ý, tiếp tục sang phase planning (gsd-plan-phase) để:
   - Thống nhất contract (ví dụ: thêm field chunk-level hoặc html safe content).
   - Thêm rate-limit / caching nếu cần.
2. Viết tests bổ sung (integration tests với DB thật hoặc mocked Qdrant) nếu cần.

File liên quan trong repo
- `api/v1/endpoints.py` — định nghĩa route
- `api/models.py` — Pydantic models cho request/response
- `core/rag_pipeline.py` — định nghĩa luồng lấy article và hydrate
- `retrievers/sqlite_retriever.py` — logic fetch canonical article rows

Nếu bạn muốn, tôi có thể cập nhật thêm:
- một trang docs ngắn trong README root (nếu cần),
- endpoint chuyên cho `GET /articles/{article_uuid}` trả full_content (ps: hiện tại POST /search-articles hỗ trợ article_uuid),
- hoặc thêm ví dụ curl/PowerShell sẵn sàng.

---
Tôi đã tạo file này tại: `docs/search_articles.md` trong workspace. Bạn muốn tôi cập nhật README root hay tạo thêm ví dụ trực tiếp (curl/PowerShell) ở cuối file không? 

