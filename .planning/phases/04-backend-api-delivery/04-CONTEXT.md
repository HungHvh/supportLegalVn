# Phase 4: Backend API Delivery - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose the optimized Legal RAG pipeline via a high-performance FastAPI backend. This phase focuses on infrastructure robustness, streaming responses (SSE), structured data delivery, and clean lifecycle management of project singletons.

</domain>

<decisions>
## Implementation Decisions

### API Architecture & Schema
- **D-01: Structured JSON Payload:** All endpoints (except streaming) will return a structured response model.
    - **Schema:** `{"answer": str, "citations": List[Dict], "detected_domains": List[str], "confidence_score": float}`.
- **D-02: FastAPI Framework:** Use FastAPI for its native async support and automatic OpenAPI documentation.
- **D-03: Versioned API:** Prefix all endpoints with `/api/v1` (e.g., `/api/v1/ask`).

### Real-Time Interaction
- **D-04: Streaming Support (SSE):** Implement Server-Sent Events (SSE) for the `/ask` endpoint to provide a "typing" effect and improve perceived performance (TTFB).
- **D-05: Async Integration:** Refactor the `LegalRAGPipeline` and its retrievers to be fully `async` to prevent blocking the FastAPI event loop.

### Lifecycle & State Management
- **D-06: Lifespan Context Manager:** Use FastAPI `lifespan` to manage the initialization and graceful shutdown of the `LegalRAGPipeline`, `QdrantClient`, and `SQLite` connections.
- **D-07: Singleton Pattern:** Ensure that model weights and database connections are loaded once and shared across all request threads.

### Connectivity & Security
- **D-08: Environment-Based CORS:** Configure `CORSMiddleware` using an environment variable `ALLOWED_ORIGINS`. Default to `*` for local POC development but allow restriction for production.
- **D-09: Dependency Injection:** Use FastAPI `Depends` for providing the pipeline instance to route handlers.

### Error Handling
- **D-10: Business vs. System Errors:**
    - **No Documents Found:** Return `200 OK` with a polite "No information found" answer and an empty `citations` list.
    - **LLM Failures (Rate Limit/Timeout):** Return `429 Too Many Requests` or `503 Service Unavailable` with detailed error messages in the body.
- **D-11: Standardized Error Responses:** Use custom FastAPI exception handlers to ensure all errors return a consistent JSON format.

</decisions>

<specifics>
## Specific Ideas

- "TTFB is king: use SSE to stream text immediately while gathering metadata in the background or at the end."
- "Structured JSON is the foundation for future Multi-Agent orchestration."
- "FastAPI lifespan ensures we don't leak database connections when the app restarts."

</specifics>

<canonical_refs>
## Canonical References

### Project Core
- `.planning/PROJECT.md` — Vision and core values.
- `.planning/ROADMAP.md` — Phase 4 goal: Backend API Delivery.
- `.planning/REQUIREMENTS.md` — Requirement ID API-01.

### Implementation References
- `core/rag_pipeline.py` — The core logic to be exposed.
- `core/classifier.py` — Domain detection logic.
- `retrievers/` — Data access layer.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LegalRAGPipeline`: Already implements the RRF fusion and IRAC formatting.
- `LegalQueryClassifier`: Provides the domain labels for the structured response.

### Integration Points
- Need to add `fastapi`, `uvicorn`, and `sse-starlette` to `requirements.txt`.
- The `main.py` prototype will be replaced by a proper `app.py` or `api/` package structure.

</code_context>

<deferred>
## Deferred Ideas

- **User Authentication:** Remains out of scope for the POC.
- **Admin Dashboard:** Document management UI remains deferred.

</deferred>

---

*Phase: 04-backend-api-delivery*
*Context gathered: 2026-04-26*
