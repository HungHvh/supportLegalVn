# Phase 1: Persistent Foundation - Research

## Executive Summary
This research focuses on transitioning the supportLegal system from a volatile prototype (`:memory:`) to a persistent, Dockerized infrastructure capable of handling 3.6GB of Vietnamese legal text. Key findings include optimal Docker volume strategies for Qdrant, SQLite performance tuning via memory mapping and WAL mode, and a decoupling strategy for embedding models.

## 1. Qdrant Persistence & Infrastructure

### Docker Volume Strategy
As per user decision, we will use a **bind mount** to a local directory (`./qdrant_data`), but we must account for the following:
*   **WSL2/Windows Caution**: Bind mounts from NTFS/Windows directories directly into Qdrant can cause performance degradation or data corruption due to differing file system locking mechanisms.
*   **Permissions**: The `./qdrant_data` folder on the host must be writable by the user running the Docker container (typically UID 1000).

### Connectivity (Docker Network)
*   Creating a dedicated network (`legal-network`) allows us to use service-name discovery (e.g., `http://qdrant:6333`).
*   **Port Mapping**: 6333 (REST) and 6334 (gRPC).

### Recommended Config (docker-compose.yml)
```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: legal-qdrant
    volumes:
      - ./qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
      - "6334:6334"
    networks:
      - legal-network

networks:
  legal-network:
    name: legal-network
```

## 2. SQLite for 3.6GB Metadata

### Performance Tuning (PRAGMAs)
To handle 3.6GB efficiently, standard SQLite defaults are insufficient:
*   **WAL Mode**: `PRAGMA journal_mode = WAL;` allows concurrent readers and one writer without blocking.
*   **Memory Mapping**: `PRAGMA mmap_size = 3000000000;` (approx 3GB). This tells the OS to map the DB file into memory, drastically reducing syscall overhead for reads.
*   **Page Size**: `PRAGMA page_size = 4096;` (Standard, but worth ensuring).

### Optimized FTS5 Strategy
*   **External Content Tables**: The most critical optimization for Phase 1. By pointing the FTS5 virtual table to an external metadata table, we avoid duplicating the 3.6GB of text in the index.
*   **Vietnamese Tokenization**: Use `tokenize='unicode61 remove_diacritics 0'` to correctly handle Vietnamese characters and preserve diacritics, which is essential for legal precision.
*   **FTS5 Optimization**: Periodically running `INSERT INTO fts_table(fts_table) VALUES('optimize');` merges segment trees.

## 3. Embedding Interface (Decoupling)

To satisfy the requirement for model flexibility, we will implement a standard **Abstract Base Class (ABC)** pattern.

### The Interface
```python
from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def batch_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        pass
```

### Initial Implementation
The `VietnameseSBERTProvider` will implement this interface using the current `keepitreal/vietnamese-sbert` model, ensuring that the rest of the application only interacts with the `EmbeddingProvider` abstraction.

## 4. Secrets & Configuration
*   **Environment**: A `.env` file will store `QDRANT_URL`, `GEMINI_API_KEY`, `HUGGINGFACE_TOKEN`, and `DB_PATH`.
*   **Validation**: The application will use `pydantic-settings` to validate presence and types of these variables at startup.

## Validation Architecture
To verify this infrastructure, we will use:
1.  **Connectivity Health-Checks**: Automated verification that Qdrant is reachable via its health endpoint.
2.  **Persistence Test**: Insert a record, restart the container, and verify the record still exists.
3.  **FTS5 External Content Test**: Verify search results match raw table content without duplication.

---
*Research Completed: 2026-04-24*
