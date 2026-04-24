# Requirements: supportLegal

**Defined**: 2026-04-24
**Core Value**: Provide accurate, context-aware legal information from the full Vietnamese legal corpus with high precision via pre-query classification.

## v1 Requirements

### Infrastructure & Scaling
- [ ] **INF-01**: Persistent Qdrant instance running in Docker with correct vector size (768).
- [ ] **INF-02**: Optimized SQLite database schema for 3.6GB metadata storage.
- [ ] **INF-03**: Dockerized environment for the background indexer and FastAPI backend.

### Data Ingestion (Indexer)
- [ ] **ING-01**: Background script to stream full Hugging Face dataset.
- [ ] **ING-02**: Chunking strategy preserving legal hierarchy (Markdown headers).
- [ ] **ING-03**: Idempotent indexing (avoid duplicate documents if restarted).
- [ ] **ING-04**: Progress tracking and logging for long-running indexing.

### Query Processing (Classifier)
- [ ] **CLS-01**: Prompt-engineered Gemini tool to classify question into legal domain.
- [ ] **CLS-02**: Mapping of legal domains to metadata filter keys.

### RAG Pipeline
- [ ] **RAG-01**: Retrieval logic supporting pre-filters from the classifier.
- [ ] **RAG-02**: Hybrid search (Vector + FTS5) with RRF fusion.
- [ ] **RAG-03**: Citation-aware generation using Gemini (citing Law/Document Number).

### Backend API
- [ ] **API-01**: FastAPI endpoint `/ask` for POSTing questions.
- [ ] **API-02**: Endpoint to check indexing status.
- [ ] **API-03**: Environment-driven configuration (No hardcoded API keys).

## v2 Requirements
- **USER-01**: User accounts and query history.
- **DOCS-01**: UI for manual document uploads.
- **FBK-01**: Thumbs up/down feedback on LLM answers.

## Out of Scope
| Feature | Reason |
|---------|--------|
| User Auth | Not required for POC. |
| Chat Frontend | Focus is on Backend API for this milestone. |
| Real-time document updates | Initial bulk indexing is the focus. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INF-01 | Phase 1 | Pending |
| INF-02 | Phase 1 | Pending |
| INF-03 | Phase 1 | Pending |
| ING-01 | Phase 2 | Pending |
| ING-02 | Phase 2 | Pending |
| ING-03 | Phase 2 | Pending |
| CLS-01 | Phase 3 | Pending |
| CLS-02 | Phase 3 | Pending |
| RAG-01 | Phase 3 | Pending |
| RAG-02 | Phase 3 | Pending |
| RAG-03 | Phase 3 | Pending |
| API-01 | Phase 4 | Pending |
| API-02 | Phase 2 | Pending |
| API-03 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-24*
*Last updated: 2026-04-24 after initial definition*
