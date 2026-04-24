# Context: Phase 2 - Full Scale Indexing

This document captures the implementation decisions for Phase 2, finalized after discussion with the user. These decisions guide the researcher and planner.

---

## 1. Ingestion Architecture

- **Approach**: Robust single-script streaming.
- **Library**: `datasets` with `streaming=True` to handle the 3.6GB dataset without excessive RAM usage.
- **Performance**: Use batched embedding (`model.encode(batch, batch_size=64)`) and batched Qdrant upserts (100 points per call).
- **Concurrency**: Stick to single-threaded sequential processing to simplify state management and idempotency, relying on batching for speed.

## 2. Chunking & Processing

- **Strategy**: Hybrid Structural + Length-based Splitting.
- **Steps**:
    1. **Markdown Split**: Use `MarkdownHeaderTextSplitter` on headers `#`, `##`, `###` to preserve document structure (Chapters, Sections, Articles).
    2. **Length Split**: If a markdown chunk exceeds **1000 characters**, sub-split it using `RecursiveCharacterTextSplitter` with `chunk_size=1000` and `chunk_overlap=200`.
- **Metadata**: Every chunk must retain:
    - `document_id` (original HF dataset ID)
    - `so_ky_hieu` (document number)
    - `headers` (contextual headers path)
    - `chunk_hash` (for future deduplication if needed)

## 3. Idempotency & Progress Tracking

- **Tracking Mechanism**: Persistent SQLite table named `indexing_status`.
- **Schema**: `document_id TEXT PRIMARY KEY, processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`.
- **Workflow**:
    - Before processing a document from HF stream, check `indexing_status`.
    - If ID exists, skip.
    - After successful insertion of all chunks for a document into Qdrant and SQLite, insert ID into `indexing_status` and commit transaction.

## 4. Storage Integration

- **Qdrant**: Connect to `localhost:6333` (Dockerized service from Phase 1).
- **SQLite**: Use the persistent `.db` file established in Phase 1.
- **Connection Management**: Ensure both clients use persistent connections or context managers to handle high-volume writes gracefully.

## 5. Observability

- **Logging**: Use `tqdm` or structured logging to show:
    - Percentage of documents processed.
    - Time per batch.
    - Errors/Failures per document (log to a separate `errors.log`).

---
*Created: 2026-04-24*
