# Plan: Phase 16 - Stream API Integration

## Goal
Chuyển đổi API `/ask` sang `/stream` (SSE) để giảm perceived latency, gửi Citations ngay từ frame đầu tiên và hỗ trợ cập nhật Badge phân loại động trên Frontend.

## Depends on
- Phase 14: Frontend Chat History Retention and RAG Context Loop
- Phase 15: UI Legal Tags & Rerank

## Analysis & Risks
- **Risk**: Race conditions khi cập nhật nội dung message trong React state liên tục.
- **Mitigation**: Sử dụng functional updates `setMessages(prev => ...)` và tối ưu hóa re-render.
- **Risk**: LLM ngắt quãng giữa chừng gây lỗi JSON parse.
- **Mitigation**: Bọc `try-except` trong generator và gửi event `type: error`.

## Waves & Tasks

### Wave 1: Backend Protocol & Streaming Logic
- **Task 1.1**: Cập nhật `LegalRAGPipeline.astream_query` trong `core/rag_pipeline.py`.
  - Thay đổi trả về từ `AsyncGenerator[str]` sang `AsyncGenerator[Dict[str, Any]]`.
  - Yield frame đầu tiên với `type: citations`.
  - Chạy Classifier song song (async task) và yield frame `type: classification` ngay khi có kết quả.
  - Yield các frame `type: token`.
- **Task 1.2**: Cập nhật endpoint trong `api/v1/endpoints.py`.
  - Triển khai `GET /api/v1/stream` để hỗ trợ chuẩn `EventSource`.
  - Thêm helper `_parse_chat_history` để giải mã Base64 từ URL query params.
  - Thêm các header chống buffering (`X-Accel-Buffering`, `Cache-Control`).
  - Thêm padding rác (2KB) ở đầu stream để phá vỡ buffer của các phần mềm diệt virus (Bitdefender).

### Wave 2: Frontend Streaming Integration
- **Task 2.1**: Cập nhật `handleSendMessage` trong `frontend/src/app/page.tsx`.
  - Triển khai helper `encodeBase64` để gửi `chat_history` qua URL.
  - Sử dụng đối tượng `EventSource` thay vì `fetch` để tối ưu streaming.
  - Cập nhật state messages theo thời gian thực dựa trên `onmessage`.
- **Task 2.2**: Cập nhật `ChatSidebar.tsx` để hỗ trợ hiển thị Badge phân loại.
  - Thêm UI Tag cho các domains (Hình sự, Dân sự...) với màu sắc theo UI-SPEC.
  - Thêm hiệu ứng cursor khi `streaming: true`.

## Verification Criteria
### Automated Tests
- [ ] `pytest tests/test_api.py` (cập nhật test case cho stream format mới).
- [ ] Kiểm tra backend yield đúng 4 loại event: `citations`, `token`, `classification`, `done`.

### Manual UAT
- [ ] Gửi câu hỏi, xác nhận khung bên trái (`MainPane`) hiện văn bản luật ngay lập tức.
- [ ] Xác nhận chữ được "gõ" ra dần dần thay vì hiện cả khối.
- [ ] Xác nhận Badge lĩnh vực luật xuất hiện sau khi text bắt đầu chạy.
