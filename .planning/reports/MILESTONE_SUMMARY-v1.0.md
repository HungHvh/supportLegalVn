# Milestone Summary: v1.0 MVP - supportLegal

**Generated:** 2026-04-26
**Project:** supportLegal (Vietnamese Legal RAG)
**Status:** Completed (Infrastructure, Indexing, Smart RAG, API)

---

## 1. Overview
The **v1.0 MVP** milestone focused on transforming a proof-of-concept script into a production-grade RAG backend for Vietnamese legal documents. We successfully built a system capable of indexing 3.6GB of legal text, classifying queries into specialized domains, and generating citation-accurate answers using the IRAC framework.

## 2. Architecture
- **Vector Store**: Qdrant (Dockerized) for semantic similarity search.
- **Relational/FTS**: SQLite FTS5 for precise keyword matching and metadata storage.
- **LLM Engine**: Gemini 1.5 Flash for query classification and response generation.
- **Retrieval Strategy**: Hybrid Search with **Reciprocal Rank Fusion (RRF)** (Weight: 60% Keyword / 40% Vector).
- **Backend**: FastAPI (Async) with SSE streaming support.

## 3. Phases Recap
- **Phase 1: Persistent Foundation**: Established the Dockerized storage layer and environment configuration.
- **Phase 2: Full Scale Indexing**: Implemented a robust, idempotent indexer for massive data ingestion from Hugging Face.
- **Phase 3: Smart Retrieval & RAG**: Developed the Gemini-based domain classifier and implemented the IRAC generation logic with strict citation formatting.
- **Phase 4: Backend API Delivery**: Exposed the pipeline via a versioned, async FastAPI service with streaming capabilities.

## 4. Key Decisions
- **D-Hybrid Search**: Prioritized keyword search (FTS5) for legal term precision while using vectors for semantic breadth.
- **D-Pre-Query Classification**: Using an LLM to detect legal domains (Civil, Criminal, etc.) to apply targeted metadata filters before retrieval.
- **D-IRAC Generation**: Standardized responses into Issue, Rule, Analysis, and Conclusion to meet professional legal standards.
- **D-Mock Resilience**: Implemented a fallback mechanism in the API to allow service availability even during AI model initialization failures.

## 5. Requirements Coverage
- ✓ **INF-01**: Dockerized persistence layer.
- ✓ **ING-01**: High-volume data streaming and chunking.
- ✓ **CLS-01**: Multi-label legal domain classification.
- ✓ **RAG-01**: Citation-aware answer generation.
- ✓ **API-01**: Versioned async API with streaming.

## 6. Known Tech Debt & Future Work
- **T-Embedding Latency**: The `sentence-transformers` model on CPU is the primary bottleneck. Consideration for GPU acceleration or a managed embedding API is recommended.
- **T-Evaluation Coverage**: While RAGAS was explored, a continuous evaluation loop (CI/CD integration) is still pending.
- **F-Frontend**: A user interface (Web or Mobile) is required to expose the `/api/v1/stream` endpoint to end-users.

## 7. Getting Started for New Team Members
1.  **Clone & Setup**: `pip install -r requirements.txt`.
2.  **Infrastructure**: `docker-compose up -d`.
3.  **Data**: Run `indexer.py` (requires ~4GB disk space).
4.  **Backend**: `uvicorn app:app --reload`.
5.  **Docs**: Explore the API at `http://localhost:8000/docs`.

---
*Created by Antigravity AI*
