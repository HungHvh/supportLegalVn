# Roadmap: supportLegal

## Overview

We are evolving the supportLegal prototype from a single-script POC into a scalable, Dockerized RAG backend. The journey moves through infrastructure setup, massive data indexing, specialized legal query classification, and finally the FastAPI backend integration.

## Phases

- [x] **Phase 1: Persistent Foundation** - Dockerized Qdrant and optimized SQLite setup.
- [ ] **Phase 2: Full Scale Indexing** - Background worker for 3.6GB dataset ingestion.
- [ ] **Phase 3: Smart Retrieval & RAG** - Gemini classification and citation-aware generation.
- [ ] **Phase 4: Backend API Delivery** - FastAPI endpoint and pipeline integration.

## Phase Details

### Phase 1: Persistent Foundation
**Goal**: Establish the persistent storage and configuration layer.
**Depends on**: Nothing
**Requirements**: INF-01, INF-02, INF-03, API-03
**Success Criteria**:
  1. Qdrant is running in Docker and reachable.
  2. SQLite schema is created with FTS5 enabled.
  3. `.env` system is working for API keys (Gemini, HuggingFace).
**Plans**: 2 plans
- [x] 01-01: Docker and Environment configuration.
- [x] 01-02: Optimized Database Schema (SQLite + Qdrant init).

### Phase 2: Full Scale Indexing
**Goal**: Process the complete 3.6GB dataset into the persistent databases.
**Depends on**: Phase 1
**Requirements**: ING-01, ING-02, ING-03, ING-04, API-02
**Success Criteria**:
  1. Indexer script can stream and process the HF dataset.
  2. Data is persistent in Qdrant and SQLite after script completion.
  3. Progress is observable via logs/status.
**Plans**: 2 plans
- [ ] 02-01: Background Indexer Implementation (Streaming & Chunking).
- [ ] 02-02: Progress Tracking and Idempotency logic.

### Phase 3: Smart Retrieval & RAG
**Goal**: Implement the specialized legal classifier and the full retrieval/generation logic.
**Depends on**: Phase 2
**Requirements**: CLS-01, CLS-02, RAG-01, RAG-02, RAG-03
**Success Criteria**:
  1. Gemini correctly classifies queries into legal domains.
  2. Retrieval uses domains as metadata filters to improve precision.
  3. LLM summarizes results with citations to specific laws.
**Plans**: 2 plans
- [ ] 03-01: LLM Classifier and Metadata Filtering.
- [ ] 03-02: Generation Pipeline with Citations.

### Phase 4: Backend API Delivery
**Goal**: Expose the RAG pipeline via a clean FastAPI backend.
**Depends on**: Phase 3
**Requirements**: API-01
**Success Criteria**:
  1. `/ask` endpoint returns accurate legal answers.
  2. API is robust and ready for frontend integration.
**Plans**: 1 plan
- [ ] 04-01: FastAPI Backend and Endpoint integration.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Persistent Foundation | 2/2 | Complete | 2026-04-24 |
| 2. Full Scale Indexing | 0/2 | Not started | - |
| 3. Smart Retrieval & RAG | 0/2 | Not started | - |
| 4. Backend API Delivery | 0/1 | Not started | - |

---
*Last updated: 2026-04-24 after initialization*
