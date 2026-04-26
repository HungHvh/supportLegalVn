# Research: Phase 5 - Hierarchical Structural Chunking

## 1. Optical & Layout Parsing (PDF to Markdown)

### 1.1 LlamaParse (Recommended for POC)
- **Strengths**: Vision-LLM based, excellent at preserving table structure and complex layouts. Handles Vietnamese diacritics natively.
- **Pricing**:
    - **Free Tier**: 10,000 credits/month.
    - **Agentic Tier**: 10 credits/page (~$0.0125). Yields ~1,000 free pages/month.
    - **Cost Effective Tier**: 3 credits/page (~$0.00375). Yields ~3,333 free pages/month.
- **Recommendation**: Best for high-precision extraction of messy scan documents.

### 1.2 Marker-pdf (Recommended for Scale)
- **Strengths**: Open-source, vision-based layout detection, high-speed, local execution (no cost per page).
- **Recommendation**: Best for large-scale processing of the full 3.6GB corpus to avoid SaaS costs.

## 2. Semantic Regex Patterns

For Vietnamese legal documents, the following patterns have been tested and verified:

| Level | Pattern | Example Match |
|-------|---------|---------------|
| **Phần** | `r'^Phần\s+.*?\.'` | `PHẦN THỨ NHẤT.` |
| **Chương** | `r'^Chương\s+.*?\.'` | `Chương I.` |
| **Mục** | `r'^Mục\s+.*?\.'` | `Mục 1.` |
| **Điều** | `r'^Điều\s+\d+.*?\.'` | `Điều 1.`, `Điều 12.` |
| **Khoản** | `r'^\d+\.'` | `1.`, `2.` |
| **Điểm** | `r'^[a-z]\)'` | `a)`, `b)` |

**Implementation Requirements**:
- Use `re.MULTILINE` and `re.IGNORECASE`.
- Handle Unicode (UTF-8) correctly.

## 3. Qdrant Hybrid Search (Dense + Sparse)

### 3.1 Architecture
- **API**: Use Qdrant's **Universal Query API** (v1.10+).
- **Fusion**: **Reciprocal Rank Fusion (RRF)** to merge Dense and Sparse results.
- **Dense Vector**: Vietnamese-SBERT (768 dims) for semantic meaning.
- **Sparse Vector**: BM25 or SPLADE for keyword precision (e.g., matching "Điều 30").

### 3.2 Context Injection Strategy
- **Format**: `[Law Name > Chapter > Article > Clause] \n [Chunk Content]`
- **Reasoning**: This "breadcrumb" header within the chunk body ensures that keyword search (Sparse) and semantic search (Dense) both benefit from the structural context.

## 4. Common Pitfalls
- **PDF Artifacts**: Headers, footers, and page numbers can break regex. Layout parsing (Step 1) must strip these before semantic parsing (Step 2).
- **Nested Lists**: Distinguishing a "Khoản" (numbered list) from a standard list requires checking context (is it inside an Article?).
- **Encoding**: Windows console encoding (CP1252) often fails with Vietnamese text; use UTF-8 for all file operations and logs.

---
*Created: 2026-04-26*
