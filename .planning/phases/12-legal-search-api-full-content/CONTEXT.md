# Phase 12: Legal Search API for Full Content Retrieval

## Overview
This phase focuses on implementing a dedicated search API to retrieve full legal articles and documents. This serves as a "Source Viewer" capability for the frontend, allowing users to see the original raw content associated with RAG answers.

## Problem Statement
While the RAG pipeline provides summarized answers with citations, users often need to verify the full text of the law. Currently, the system lacks an efficient way to fetch the "Parent" article or full law content quickly for display in the UI.

## Objectives
- Implement `/api/v1/search-articles` endpoint.
- Support search by Law ID, Article Number, or Keywords.
- Integrate with existing SQLite article store.
- Provide structured JSON responses for frontend consumption.

## Implementation Decisions

### 1. Interface & Filtering
- **Input**: `query` (string, optional), `article_uuid` (string, optional), `doc_type` (string, optional), `top_k` (int, default 10).
- **Filtering**: If `doc_type` is provided, filter results by document type (e.g., "Luật", "Nghị định").

### 2. Search & Highlighting
- **Highlighting**: Use SQLite FTS5 `highlight()` function to wrap matching terms in `full_content` (or a snippet) with `<b>` tags or similar.
- **Result Count**: Limit to top 10 results for keyword searches. Pagination is deferred to future phases.

### 3. Response Structure
- Return a list of objects containing: `article_uuid`, `doc_id`, `so_ky_hieu`, `title`, `score`, `full_content` (with highlights), and `doc_type`.

## Out of Scope (Deferred)
- Pagination (offset/page support).
- Automatic related article linking (will be a separate API/Phase later).

## Success Criteria
- [ ] API endpoint returns full article content for a given citation.
- [ ] Keyword search returns results with highlighted matches.
- [ ] Filtering by `doc_type` works correctly.
- [ ] Search performance remains sub-200ms.
