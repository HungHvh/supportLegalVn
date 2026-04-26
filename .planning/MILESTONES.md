# Milestones: supportLegal

## ✅ v1.2 Quality Assurance (2026-04-26)
**Status:** Shipped
**Phases:** 1-6
**Plans:** 10
**Tasks:** ~40
**Metrics:** +31% Hit Rate gain via Hybrid RRF + Hierarchical Chunking.

### Delivered
- **Infrastructure**: Persistent Qdrant & SQLite in Docker.
- **Ingestion**: Idempotent HF streaming indexer.
- **RAG Engine**: Smart classifier + Hybrid search + IRAC generation.
- **API**: Async FastAPI with streaming support.
- **Optimization**: Legal-specific hierarchical parsing.
- **Validation**: Quantitative benchmark report.

### Key Decisions
- **Custom Legal Parser**: Necessary to handle Vietnamese legal document structure (Phần > Chương > Điều).
- **Docker-Mandatory**: Resolved ML library DLL issues on Windows.

### Known Gaps
- **Validation Cleanup**: Artifact status inconsistencies resolved during final audit.
- **Evaluation Scope**: Benchmarked primarily on Election Law; further evaluation needed for broader domains.

---
*Last updated: 2026-04-26*
