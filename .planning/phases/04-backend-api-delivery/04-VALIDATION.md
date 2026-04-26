# Phase 4 — Validation Strategy

**Phase:** 4 - Backend API Delivery
**Status:** Pending

---

## 1. Automated Verification Map

| Task ID | Plan | Wave | Requirement | Target Behavior | Test Command |
|---------|------|------|-------------|-----------------|--------------|
| 04-01-01| 01 | 1 | INF-01 | FastAPI starts with lifespan | `pytest tests/test_lifespan.py` |
| 04-01-02| 01 | 1 | API-02 | Async Qdrant retrieval | `pytest tests/test_async_retrieval.py` |
| 04-01-03| 01 | 2 | API-03 | Async SQLite retrieval | `pytest tests/test_async_retrieval.py` |
| 04-02-01| 02 | 1 | API-01 | /ask returns structured JSON | `pytest tests/test_api_endpoints.py` |
| 04-02-02| 02 | 1 | API-04 | /stream returns SSE tokens | `pytest tests/test_streaming.py` |

## 2. UAT Scenarios (Conversational)

| Scenario | Input | Expected Outcome |
|----------|-------|------------------|
| **Valid Query** | "Thủ tục kết hôn" | JSON with answer (IRAC), citations (Luật Hôn nhân gia đình), and status 200. |
| **No Results** | "Công nghệ nano 2030" | JSON with status 200, answer "Không tìm thấy...", citations empty. |
| **Stream Test** | "Luật doanh nghiệp 2020" | Immediate first token via SSE, final frame contains citations. |

## 3. Performance Gates

- **TTFB (Streaming):** < 500ms
- **Total Answer Latency:** < 5s (for average 200 token response)
- **Concurrent Requests:** Support 5 simultaneous users on POC hardware.

---
*Created: 2026-04-26*
