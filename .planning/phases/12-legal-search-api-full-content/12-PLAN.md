---
wave: 1
depends_on: []
files_modified:
  - api/models.py
  - api/v1/endpoints.py
  - retrievers/sqlite_retriever.py
autonomous: true
---

# Phase 12: Legal Search API for Full Content Retrieval - Execution Plan

## Context
The API endpoint `/api/v1/search-articles` exists but needs to support `doc_type` filtering and highlight the matched query in the response. Since full article content is not indexed in FTS5 (only chunks and titles are), highlighting will be implemented via Python string replacement on the full content, and `doc_type` filtering will be mapped to `so_ky_hieu` patterns.

## Goal
Update the search API to fully satisfy the decisions in CONTEXT.md.

## Tasks

<task>
<description>Update Search Models</description>
<read_first>
- api/models.py
</read_first>
<action>
Modify `api/models.py`:
1. In `SearchArticlesRequest`, add `doc_type: Optional[str] = None`.
2. In `ArticleResult`, add `doc_type: Optional[str] = None` and `highlighted_content: Optional[str] = None`.
</action>
<acceptance_criteria>
- `api/models.py` contains `doc_type` field in `SearchArticlesRequest`
- `api/models.py` contains `highlighted_content` field in `ArticleResult`
</acceptance_criteria>
</task>

<task>
<description>Implement Keyword Highlighting and DocType Filtering in Retriever</description>
<read_first>
- retrievers/sqlite_retriever.py
</read_first>
<action>
Modify `retrievers/sqlite_retriever.py`:
1. In `aretrieve_articles_by_title`, add a `doc_type: Optional[str] = None` parameter.
2. If `doc_type` is provided, append a condition to the WHERE clause to filter by `la.so_ky_hieu`. Map common `doc_type` strings: e.g., "Luật" -> `la.so_ky_hieu LIKE '%Luật%'`, "Nghị định" -> `la.so_ky_hieu LIKE '%NĐ-CP%'`, "Thông tư" -> `la.so_ky_hieu LIKE '%TT-%'`. If not matched to a specific rule, do `la.so_ky_hieu LIKE '%' || ? || '%'`.
3. Create a helper method `_highlight_text(text: str, query: str) -> str` that performs case-insensitive regex replacement to wrap matches of `query` in `<b>...</b>`.
4. The helper will be used in the endpoint, not the retriever (since retriever returns TextNode). But for now, ensure `aretrieve_articles_by_title` correctly handles the `doc_type` filter.
</action>
<acceptance_criteria>
- `sqlite_retriever.py` contains `doc_type` parameter in `aretrieve_articles_by_title`
- `sqlite_retriever.py` contains SQL logic handling `la.so_ky_hieu LIKE` when `doc_type` is present
</acceptance_criteria>
</task>

<task>
<description>Update Search Endpoint Logic</description>
<read_first>
- api/v1/endpoints.py
</read_first>
<action>
Modify `api/v1/endpoints.py` -> `search_articles`:
1. Pass `request.doc_type` to `pipeline.retriever.aretrieve` (you may need to update `LegalHybridRetriever` to accept and pass `doc_type`, or call `fts_retriever` directly if preferred). Alternatively, update `LegalHybridRetriever.aretrieve` to accept `doc_type` as kwargs or process it.
*Correction for Action*: Since `pipeline.retriever` is a `LegalHybridRetriever`, which doesn't natively take `doc_type` in `aretrieve(q)`, modify the endpoint to directly call `fts_retriever.aretrieve_articles_by_title(q, top_k=request.top_k, doc_type=request.doc_type)` instead of using the hybrid retriever for this specific "source viewer" lookup. 
2. In the response formatting loop, use a simple regex to replace the `request.query` (case-insensitive) with `<b>\g<0></b>` in the `full_content` to populate the `highlighted_content` field.
3. Map the `doc_type` in the response based on `so_ky_hieu`.
</action>
<acceptance_criteria>
- `api/v1/endpoints.py` calls `fts_retriever.aretrieve_articles_by_title` directly in `search_articles`
- `api/v1/endpoints.py` contains regex replacement logic for `<b>` tags
</acceptance_criteria>
</task>

## Verification
- Run `pytest tests/test_search_articles.py` to ensure existing tests pass.
- Start the server and send a request with `doc_type="Nghị định"` and verify filtering works.
