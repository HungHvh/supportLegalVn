# Phase 3: Smart Retrieval & RAG - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the specialized legal classifier and the full retrieval/generation logic. This includes domain-aware query classification using Gemini, hybrid search optimization (Vector + FTS5), and citation-aware answer generation following the IRAC framework.

</domain>

<decisions>
## Implementation Decisions

### Query Classification Strategy (Chiến lược phân loại truy vấn)
- **D-01: Domain Recognition:** Gemini will classify queries into 6 high-impact domains:
    - **Civil & Family (Dân sự & Hôn nhân Gia đình):** Inheritance, civil contracts, divorce, property rights.
    - **Criminal (Hình sự):** Crimes, penalties, criminal proceedings.
    - **Business & Commercial (Doanh nghiệp & Thương mại):** Company formation, bankruptcy, commercial contracts, intellectual property.
    - **Labor & Insurance (Lao động & Bảo hiểm):** Labor contracts, dismissal, social insurance (BHXH), health insurance (BHYT).
    - **Administrative & Tax (Hành chính & Thuế):** Traffic violations, tax regulations, administrative procedures.
    - **Land & Real Estate (Đất đai & Bất động sản):** Land titles (Sổ đỏ), land disputes, transfers.
- **D-02: Multi-label Classification:** Allow a single query to belong to multiple domains simultaneously to handle legal intersections.
- **D-03: "Unknown" Handling:** If confidence score is low, assign the "General" label. This bypasses domain filtering and defaults to a full-corpus search.

### Retrieval Filtering & Precision (Lọc và độ chính xác)
- **D-04: Soft Boost Preference:** Apply domain filters as a preference boost rather than a hard exclusion to prevent missing context from overlapping or related laws.
- **D-05: Explicit Hard Filter:** Only apply hard metadata filters if the user explicitly commands it (e.g., "Theo quy định của Luật Doanh nghiệp 2020..." or "Chỉ tìm trong bộ luật Hình sự").
- **D-06: Unified Filtering:** Apply filtering/boosting to both Vector and Keyword (FTS5) search streams before the RRF fusion step.

### Hybrid Search Tuning (RRF & Context)
- **D-07: Balancing Weights:** Weighting should be roughly **50-60% Keyword / 40-50% Vector**. Keyword precision is prioritized for specific legal terms and document numbers.
- **D-08: LLM Context Window:** Feed **5 to 8** most relevant chunks to the LLM for generation.
- **D-09: Chunk Granularity:** Chunks should ideally represent a single Article or Clause (approx. 300-500 tokens).

### Generation & Citation Style (Văn phong & Trích dẫn)
- **D-10: Strict Citation Formatting:** Citations must follow the standard Vietnamese format: *“Theo [Khoản X], [Điều Y], [Tên văn bản/Số hiệu văn bản] (Năm ban hành)...”*.
- **D-11: Hybrid Response Tone (IRAC):**
    - **Issue/Conclusion:** Direct, conversational answer first.
    - **Rule:** Strict formal legal citations.
    - **Analysis/Application:** Explanatory breakdown of how the law applies to the user's specific context.
- **D-12: Mandatory Disclaimer:** Every response must include a legal disclaimer stating the information is for reference only.

### the agent's Discretion
- Exact threshold for "low confidence" in classification.
- Specific RRF constant (K) tuning (starting with K=60 from prototype).
- Prompt engineering details for multi-label classification and IRAC formatting.

</decisions>

<specifics>
## Specific Ideas

- "Avoid 'lost in the middle' effect by keeping context to 5-8 chunks."
- "Keyword search ensures we don't miss an Article when the user types the exact name/number."
- "IRAC framework provides the best balance between professional accuracy and user understandability."

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Core
- `.planning/PROJECT.md` — Vision and core values.
- `.planning/REQUIREMENTS.md` — Requirement IDs CLS-01, CLS-02, RAG-01, RAG-02, RAG-03.

### Implementation References
- `main.py` — Prototype for RRF fusion and hybrid search logic.
- `indexer.py` — Reference for metadata schema and chunking strategy (headers path).
- `db/sqlite.py` — FTS5 schema and query patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `VietnameseSBERTProvider` (core/embeddings.py): Provides the 768-dim vectors.
- `QdrantClient` and `sqlite3` modules: Established persistence layer.

### Established Patterns
- **Reciprocal Rank Fusion (RRF):** Already implemented in `main.py` and should be ported to the production pipeline.
- **Markdown Splitting:** Chunking logic from Phase 2 provides the structural headers used for filtering.

### Integration Points
- The classifier will be a new component in the retrieval pipeline.
- The output of this phase will feed directly into the FastAPI backend (Phase 4).

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-smart-retrieval-rag*
*Context gathered: 2026-04-26*
