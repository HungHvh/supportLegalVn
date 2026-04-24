# supportLegal

## What This Is

supportLegal is a RAG (Retrieval-Augmented Generation) system designed to provide accurate answers to questions about Vietnamese law. It utilizes a hybrid search approach (vector and keyword) combined with an LLM-based query classifier to ensure high precision across the full 3.6GB corpus of Vietnamese legal documents.

## Core Value

Provide accurate, context-aware legal information from the full Vietnamese legal corpus with high precision via pre-query classification.

## Requirements

### Validated

- ✓ **Hybrid Search Prototype** — Basic retrieval using Qdrant (in-memory) and SQLite FTS5 is functional in `main.py`.

### Active

- [ ] **Infrastructure Scaling** — Migrate to persistent Qdrant in Docker and optimized SQLite storage for a 3.6GB dataset.
- [ ] **Automated Indexer** — Separate worker script to process the full Hugging Face dataset (Vietnamese legal documents) into the vector and metadata databases.
- [ ] **Query Classification** — Gemini-based classifier to categorize user queries into specific legal domains before retrieval.
- [ ] **Full RAG Pipeline** — Integrated FastAPI backend that classifies, retrieves, and generates answers using Gemini.
- [ ] **FastAPI Backend API** — Clean API surface for interacting with the RAG system.

### Out of Scope

- **User Management** — This is a POC/Test version; authentication and profiles are deferred.
- **Document Management UI** — Automated ingestion from Hugging Face is sufficient; no manual upload UI for now.

## Context

- **Current State**: A working script `main.py` exists that processes a sample of 50 documents.
- **Data Source**: Hugging Face `vohuutridung/vietnamese-legal-documents`.
- **Tech Stack**: FastAPI, Qdrant (Docker), SQLite FTS5, Gemini (LLM), SentenceTransformers (`vietnamese-sbert`).

## Constraints

- **Storage**: Must handle a 3.6GB text dataset efficiently.
- **Precision**: Vietnamese-specific nuances in legal terminology must be handled by the embedding model and classifier.
- **Rate Limits**: LLM usage (Gemini) must be managed for large-scale classification and generation.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **Qdrant (Docker)** | Essential for persistence and scaling to the full 3.6GB dataset. | — Pending |
| **Gemini LLM** | Chosen for generation and pre-query classification. | — Pending |
| **LLM Classification** | Required to prevent retrieval mixing across unrelated legal domains. | — Pending |
| **Separate Indexer** | decouples heavy data processing from the API runtime. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-24 after initialization*
