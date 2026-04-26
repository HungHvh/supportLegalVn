# Phase 4 AI Design Contract (AI-SPEC)

**Phase:** 4 - Backend API Delivery
**Model:** Gemini 1.5 Flash (via LlamaIndex)
**Pattern:** Async Streaming RAG

## 1. Interaction Strategy

### Token Streaming (SSE)
- **Engine:** `llama_index.llms.gemini.Gemini.astream_complete`
- **Format:** `text/event-stream`
- **Payload:** Each chunk should contain a JSON string with the incremental token and eventually the metadata (citations, domains) in the final frame.

### Async Execution
- **Refactor Requirements:** All retrievers (`SQLiteFTS5Retriever`, `QdrantRetriever`) and the `LegalHybridRetriever` must be refactored to support `async`/`await`.
- **Concurrency:** Use `asyncio.gather` for parallel retrieval from SQLite and Qdrant to minimize latency.

## 2. Structured Output Schema

The non-streaming `/ask` endpoint and the final frame of the streaming endpoint must conform to:

```json
{
  "answer": "string (IRAC formatted)",
  "citations": [
    {
      "source": "string (Document number/Title)",
      "text": "string (Snippet)",
      "score": "float"
    }
  ],
  "detected_domains": ["string"],
  "confidence_score": "float"
}
```

## 3. Prompt Engineering (Async Context)

The prompt remains consistent with Phase 3 (IRAC structure), but must be managed as a `llama_index.core.PromptTemplate` injected via FastAPI dependency injection.

## 4. Evaluation Strategy (RAGAS Integration)

Phase 4 will include an optional `/eval` endpoint to trigger RAGAS evaluation on a test set (if provided) to ensure the API delivery didn't regress retrieval performance.

- **Metrics:** `faithfulness`, `answer_relevancy`, `context_precision`.
- **Target:** Maintain > 0.8 on all metrics.

---
*Created: 2026-04-26*
