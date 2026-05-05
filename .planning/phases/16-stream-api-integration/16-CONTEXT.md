# Context: Phase 16 - Stream API Integration

## Domain Boundary
Chuyển đổi API `/ask` (đồng bộ) sang `/stream` (SSE) và cập nhật Frontend để hỗ trợ streaming với đầy đủ metadata (citations, classification).

## Locked Decisions

### 1. Metadata Delivery Strategy (Option A)
- **Citations First**: Gửi toàn bộ danh sách trích dẫn (citations) ngay frame đầu tiên của luồng SSE.
- **Rationale**: Người dùng có thể thấy ngay các nguồn luật được tham khảo trong khi đợi LLM sinh nội dung.

### 2. SSE Event Protocol
- **Format**: Mỗi dòng dữ liệu SSE sẽ là một JSON object với trường `type`.
- **Event Types**:
  - `citations`: Gửi mảng các object trích dẫn.
  - `token`: Gửi từng phần nhỏ của nội dung câu trả lời.
  - `classification`: Gửi thông tin phân loại lĩnh vực (domains/badges).
  - `error`: Gửi thông báo lỗi nếu có sự cố giữa luồng.
  - `done`: Tín hiệu kết thúc luồng.

### 3. Classification UI Behavior
- **Async Badges**: Không đợi Classifier kết thúc mới bắt đầu stream text. 
- **Behavior**: Event `classification` sẽ được gửi ngay khi có kết quả, khiến các badge lĩnh vực luật xuất hiện động trên giao diện mà không làm chậm việc hiển thị câu trả lời đầu tiên.

### 4. Error Handling
- **Explicit Events**: Khi có lỗi phát sinh trong `event_generator`, gửi event `type: error` thay vì ngắt kết nối âm thầm.

## Canonical Refs
- `api/v1/endpoints.py`: Nơi định nghĩa các endpoint `/ask` và `/stream`.
- `core/rag_pipeline.py`: Chứa logic `acustom_query` và `astream_query`.
- `frontend/src/app/page.tsx`: Nơi gọi API từ frontend.

## Codebase Context
- **Backend**: Đã có `sse_starlette` và logic stream cơ bản nhưng thiếu trích dẫn.
- **Frontend**: Cần cập nhật cơ chế fetch từ `await response.json()` sang `ReadableStream` reader.
