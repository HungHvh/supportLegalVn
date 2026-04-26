# Validation: Phase 5 - Hierarchical Structural Chunking

## 1. Validation Architecture

We will use a combination of unit tests for the parser and end-to-end retrieval tests to verify the impact of structural chunking.

### Dimensions of Validation
1. **Dimension 1: Structural Accuracy** - Verify that `Phần`, `Chương`, `Điều`, `Khoản`, `Điểm` are correctly identified and split.
2. **Dimension 2: Metadata Integrity** - Ensure breadcrumbs (Law > Chapter > Article) are correctly inherited by child chunks.
3. **Dimension 3: Context Injection** - Confirm that the indexed text includes the hierarchical header.
4. **Dimension 4: Hybrid Search Performance** - Compare retrieval precision (mAP or Hit Rate) between old fixed-size chunks and new hierarchical chunks.
5. **Dimension 5: Robustness** - Test against "dirty" PDF outputs (broken lines, extra spaces).

## 2. Automated Tests

### Unit Tests (`tests/test_legal_parser.py`)
- [ ] `test_split_articles`: Verifies splitting text into Article nodes.
- [ ] `test_split_clauses`: Verifies splitting articles into Clause nodes.
- [ ] `test_breadcrumb_inheritance`: Ensures a "Điểm" (Point) chunk has the correct full path in metadata.
- [ ] `test_header_injection`: Verifies the final string for embedding contains the injected breadcrumb.

### Integration Tests (`tests/test_hybrid_indexer.py`)
- [ ] `test_qdrant_sparse_upsert`: Verifies that points are upserted with both dense and sparse vectors.
- [ ] `test_hybrid_query_rrf`: Verifies that RRF fusion returns relevant results for keyword-heavy queries (e.g., "Điều 30").

## 3. UAT (User Acceptance Testing)
- [ ] **Scenario 1**: Querying for a specific clause that was previously split mid-sentence.
    - *Expected*: Full clause retrieved as a single, coherent unit.
- [ ] **Scenario 2**: Querying for a general concept (e.g., "thành lập doanh nghiệp").
    - *Expected*: Results are grouped by Law/Article, making it easy to see the source.

---
*Created: 2026-04-26*
