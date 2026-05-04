# UAT: Phase 13 - Frontend Original Content Display with Highlights

**Status:** ✅ PASSED
**Date:** 2026-05-04

## Test Results

| Test Case | Description | Result | Notes |
|-----------|-------------|--------|-------|
| 1. API Integration | Check if clicking citation calls `/search-articles` | ✅ PASS | Fixed issue where query was empty due to missing metadata. |
| 2. Exact Match | Check if correct article is displayed | ✅ PASS | Switched to `article_uuid` for 100% precision instead of FTS. |
| 3. Highlight Rendering | Check if `<mark>` tags appear correctly | ✅ PASS | Parsed backend `<b>` tags successfully. |
| 4. Deduplication | Check if citations in sidebar are unique | ✅ PASS | Implemented `seen_sources` set in `rag_pipeline.py`. |
| 5. Navigation | Check Prev/Next buttons | ✅ PASS | Verified counter and navigation state. |
| 6. Auto-scroll | Check if viewer scrolls to highlight | ✅ PASS | Smooth scroll implemented in `MainPane.tsx`. |

## Issues Found & Resolved
- **Bug 1:** Frontend interface for `Citation` was out of sync with Backend (missing `metadata`). Resolved by updating TS interfaces and using `citation.source` + `citation.article_uuid`.
- **Bug 2:** Citations were duplicated if multiple chunks came from the same article. Resolved via backend deduplication.
- **Bug 3:** FTS search on `so_ky_hieu` was inaccurate for combined strings. Resolved by implementing `article_uuid` lookup.

## Verification Log
- 2026-05-04: Initial execution.
- 2026-05-04: User reported "FE không hiển thị gì".
- 2026-05-04: Diagnosed metadata sync issue. Fixed and re-built.
- 2026-05-04: User reported duplicates and search inaccuracy. Fixed via UUID and deduplication.
- 2026-05-04: Build `npm run build` PASS. Manual verification PASS.
