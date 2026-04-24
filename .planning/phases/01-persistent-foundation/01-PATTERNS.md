# Phase 1: Persistent Foundation - Patterns

## Goal
Map existing prototype patterns in `main.py` to the new persistent architecture.

## Existing Implementation (`main.py`)

### 1. Database Connections (Lines 16-52)
- **Pattern**: Direct initialization of `sqlite3.connect` and `QdrantClient(":memory:")`.
- **Constraint**: This needs to be abstracted into a connection manager or configuration module that supports Docker-based URLs.

### 2. SQLite Schema (Lines 24-39)
- **Pattern**: `chunks_metadata` (Metadata) and `chunks_fts` (Virtual Table).
- **Modification**: Current FTS table is internal content. We need to transition to **External Content** to save space on a 3.6GB dataset.

### 3. Embedding Initialization (Line 55)
- **Pattern**: `SentenceTransformer("keepitreal/vietnamese-sbert")` directly assigned to variable.
- **Modification**: Needs to be moved into a class implementing a new `EmbeddingProvider` interface.

## Target Architecture Patterns

### Configuration (`config/settings.py`)
- use `pydantic-settings` to manage:
  - `QDRANT_HOST` (default: `localhost` for local, `qdrant` for docker)
  - `DB_PATH` (default: `legal_poc.db`)
  - `EMBEDDING_MODEL_NAME` (default: `keepitreal/vietnamese-sbert`)

### Database Abstraction (`db/`)
- `db/qdrant.py`: Manage Qdrant client lifecycle and collection initialization.
- `db/sqlite.py`: Manage SQLite connection, WAL mode activation, and schema migrations.

### Interface Implementation (`services/embeddings.py`)
- Define `BaseEmbedder` interface with `async` methods.
- Implement `VietnameseSBERT` concrete class (compatible with `async`).

---
*Patterns Mapped: 2026-04-24*
