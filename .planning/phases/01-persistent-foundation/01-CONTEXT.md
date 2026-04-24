# Phase 1: Persistent Foundation - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the persistent storage and configuration layer for the supportLegal system. This includes setting up Dockerized Qdrant for vector storage and an optimized SQLite database for metadata and Full-Text Search.

</domain>

<decisions>
## Implementation Decisions

### Qdrant Persistence & Connectivity
- **D-01:** Use Docker Volume mapping to `./qdrant_data` within the project directory for easy data management.
- **D-02:** Use a shared Docker Network named `legal-network` to allow internal container communication via service names.

### SQLite Configuration
- **D-03:** Enable **WAL (Write-Ahead Logging) mode** for better performance with concurrent reads/writes.
- **D-04:** Focus on optimized FTS5 indexing to handle the 3.6GB document metadata corpus efficiently.

### Embedding Strategy
- **D-05:** Use `vietnamese-sbert` (size 768) as the primary embedding model.
- **D-06:** **Interface-first Design:** Implement the embedding logic using an Abstract Base Class or Interface to allow switching to other providers (OpenAI, Cohere) with minimal code changes.

### Secrets Management
- **D-07:** Use a `.env` file for tracking Gemini API keys, HuggingFace tokens, and configuration strings for the POC.

### the agent's Discretion
- Exact volume mount path syntax for different OS (handled by Docker Compose).
- Specific SQLite PRAGMA settings (beyond WAL mode) for maximum throughput.
- Choice of Abstract Base Class library (standard `abc` module vs other patterns).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Core
- `.planning/PROJECT.md` — Vision and core values.
- `.planning/REQUIREMENTS.md` — Requirement IDs INF-01, INF-02, INF-03, API-03.
- `main.py` — Current prototype implementation for SQLite/Qdrant logic.

### External Specs
- No external specs — requirements are fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SentenceTransformer("keepitreal/vietnamese-sbert")`: Already tested in prototype.
- `QdrantClient`: Connection logic exists, needs adaptation for Docker/Network.
- `sqlite3`: FTS5 logic exists in `main.py`, needs moving to a dedicated database module.

### Established Patterns
- **Hybrid Search**: RRF fusion logic is already prototyped and should be preserved in the new architecture.

### Integration Points
- The indexer script (Phase 2) will depend on the database modules established here.
- The FastAPI backend (Phase 4) will consume these persistent storages.

</code_context>

<deferred>
## Deferred Ideas

- User accounts and history — Phase 5+ (Out of Scope for v1).
- Cloud-based Vector DB — Using local Docker for this POC to stay within Coarse granularity.

</deferred>

---

*Phase: 01-persistent-foundation*
*Context gathered: 2026-04-24*
