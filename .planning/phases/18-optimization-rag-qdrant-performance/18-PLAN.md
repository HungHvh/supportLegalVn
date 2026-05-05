# Plan: Phase 18 - Tối ưu RAG & Qdrant - Hiệu năng

## Goal
Tối ưu hóa hiệu năng hệ thống RAG và kết nối Qdrant để giảm độ trễ và tăng khả năng xử lý đồng thời, đồng thời triển khai cơ chế Semantic Cache bền vững.

## Wave 1: Infrastructure & gRPC Migration
- [x] **Docker Config**: Cập nhật `docker-compose.yml`, đổi `QDRANT_PORT` của service `api` sang `6334`.
- [x] **Qdrant Manager Update**: Sửa `db/qdrant.py` để sử dụng `port=6334` và `prefer_grpc=True` khi khởi tạo `QdrantClient`.
- [x] **Cache Collection Setup**: Thêm logic khởi tạo collection `semantic_cache` trong `QdrantManager`.

## Wave 2: Metadata Extraction & Filtering
- [x] **Classifier Enhancement**: Cập nhật `core/classifier.py` để trích xuất `nam_ban_hanh` (năm) và `linh_vuc` (lĩnh vực) từ câu hỏi người dùng.
- [x] **Payload Indexing**: Tạo payload index cho `nam_ban_hanh`, `linh_vuc` trong collection chính và `created_at` trong collection cache.
- [x] **Retriever Filtering**: Cập nhật `retrievers/qdrant_retriever.py` để hỗ trợ tham số `query_filter` trong các hàm tìm kiếm.


## Wave 3: Semantic Cache & Background TTL Worker
- [x] **Semantic Cache Logic**: Triển khai `check_semantic_cache` và `save_to_cache` trong `db/qdrant.py`. Đảm bảo lưu kèm `created_at` và danh sách `citations` (JSON).

- [x] **Pipeline Integration**: Tích hợp cache vào `core/rag_pipeline.py` (hàm `acustom_query` và `astream_query`).
- [x] **TTL Background Worker**: Viết script `scripts/cleanup_cache.py` thực hiện query và xóa các points cũ hơn 30 ngày.
- [x] **Worker Integration**: Cấu hình khởi chạy worker này (ví dụ: thêm vào `Dockerfile` hoặc một service riêng trong `docker-compose.yml`).


## Verification (UAT)
- [x] **gRPC**: Kiểm tra log/metrics xác nhận Qdrant đang chạy qua gRPC (port 6334).
- [x] **Filtering**: Chạy test case với metadata (VD: "Luật đất đai 2024") và kiểm tra results chỉ chứa văn bản khớp filter.
- [x] **Semantic Cache**: Kiểm tra latency giảm đáng kể (>80%) khi query trùng lặp.
- [x] **TTL Worker**: Chạy script cleanup thủ công với dữ liệu mẫu cũ và xác nhận points bị xóa.


---
*Phase: 18-optimization-rag-qdrant-performance*
