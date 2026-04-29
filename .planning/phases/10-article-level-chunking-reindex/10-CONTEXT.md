# Context: Phase 10 — Article-Level Chunking & Full Re-index

Decisions locked after user discussion on 2026-04-29 (refined session). Downstream planner and executor must follow these without re-asking.

---

## Decisions

### D1 — Chunking Strategy (REVISED — replaces truncation approach)

**Decision**: Hybrid split — structural boundaries first, `RecursiveCharacterTextSplitter` as fallback.

**❌ Old (incorrect)**: Truncate enriched text to `MAX_EMBED_CHARS=800` chars → loses 70–80% of long Điều content.

**✅ New**: Split each Điều into multiple chunks, each embedded as a separate Qdrant point.

```python
MIN_CHUNK_CHARS = 50         # chars — short clause merges into parent buffer
MAX_EMBED_CHARS = 500        # tokens / chars target per chunk
CHUNK_OVERLAP   = 100        # chars overlap for RecursiveCharacterTextSplitter
MAX_CHUNKS_PER_ARTICLE = 20  # soft cap — log warning if exceeded, no hard drop

def split_article(article_node) -> list[str]:
    chunks = []
    parent_buffer = ""

    for clause in article_node.children:
        text = clause.content.strip()

        # 3.3 — short clause: merge into parent buffer (not skipped)
        if len(text) < MIN_CHUNK_CHARS:
            parent_buffer += " " + text
            continue

        # Flush parent buffer into this clause if non-empty
        if parent_buffer:
            text = parent_buffer.strip() + " " + text
            parent_buffer = ""

        # If clause is long → split further
        if len(text) > MAX_EMBED_CHARS:
            sub_chunks = recursive_splitter.split_text(text)
        else:
            sub_chunks = [text]

        for c in sub_chunks:
            chunks.append(enrich(clause.full_path, c))

    # ⚠️ POST-LOOP FLUSH — prevents trailing buffer data leak
    # Edge case: if the last N clauses are all short (< MIN_CHUNK_CHARS),
    # they accumulate in parent_buffer but the loop ends without flushing.
    # Without this, those clauses silently vanish from Qdrant + legal_chunks.
    if parent_buffer:
        chunks.append(enrich(article_node.full_path, parent_buffer.strip()))
        parent_buffer = ""

    # Fallback: no clauses → split full_content directly
    if not chunks:
        chunks = [enrich(article_node.full_path, c)
                  for c in recursive_splitter.split_text(article_node.full_content)]

    return chunks
```

**RecursiveCharacterTextSplitter config**:
```python
RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""]
)
```

**Enrichment** (what gets embedded, not stored):
```python
headers = " > ".join(doc.metadata.values())   # e.g., "115/NQ-HDBCQG > Chương I > Điều 12 > Khoản 2"
enriched = f"[{headers}] {chunk_text}"
```

**Short chunk rule (3.3)**:
- Khoản/Điểm content `< MIN_CHUNK_CHARS` → **merge into parent chunk buffer** (NOT skipped).
- Ensures legal signals like "cấm", "được phép", "phạt tiền" are never dropped silently.

---

### D2 — Article Store Architecture

**Decision**: **SQLite two-table split** (unchanged from prior session).

| Table | Purpose |
|-------|---------|
| `legal_articles` | Full Điều text — display & citation |
| `legal_chunks` | Per-chunk row — links to `legal_articles` via `article_uuid` |

```sql
CREATE TABLE legal_articles (
    article_uuid  TEXT PRIMARY KEY,
    doc_id        TEXT NOT NULL,
    so_ky_hieu    TEXT,
    article_title TEXT,
    article_path  TEXT,
    full_content  TEXT NOT NULL
);

CREATE TABLE legal_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id     TEXT UNIQUE NOT NULL,   -- UUID, also Qdrant point ID
    article_uuid TEXT NOT NULL REFERENCES legal_articles(article_uuid),
    doc_id       TEXT NOT NULL,
    so_ky_hieu   TEXT,
    level        TEXT,                   -- "KHOẢN" | "ĐIỂM" | "ARTICLE"
    chunk_path   TEXT,
    content      TEXT NOT NULL           -- raw chunk text (no header prefix)
);
```

Qdrant payload (minimal):
```json
{
  "chunk_id": "uuid",
  "article_uuid": "uuid-of-parent-dieu",
  "doc_id": "693036",
  "so_ky_hieu": "115/NQ-HDBCQG",
  "level": "KHOẢN",
  "article_title": "Điều 12. Quy định về..."
}
```

---

### D3 — Rebuild Strategy

**Decision**: **Drop & Rebuild** — clean slate.

- Drop Qdrant collection `legal_chunks`
- Drop SQLite tables: `legal_documents`, `docs_fts`, `indexing_status`, all triggers
- Recreate with new schema
- Re-index all ~518K documents from scratch

---

### D4 — Article ID Format

**Decision**: **UUID + separate `legal_articles` table** (unchanged).

---

### D5 — FTS5 Strategy (REVISED)

**Decision**: **Single FTS5 table on chunks** — `chunks_fts` (NOT `articles_fts` on full article).

**❌ Old**: `articles_fts` on `legal_articles.full_content` → keyword match is diluted over full Điều text.

**✅ New**: FTS5 on chunks → same granularity as vector search → aligned for RRF merge.

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id     UNINDEXED,        -- maps directly to Qdrant point ID
    content,                        -- indexed for keyword match
    article_title,                  -- indexed for title boost
    article_uuid UNINDEXED,
    so_ky_hieu   UNINDEXED,
    tokenize='unicode61 remove_diacritics 0'
);
```

**Title boost** (optional but recommended):
```python
if query_terms in article_title:
    fts_score *= 1.3
```

**Insert trigger** — populate `chunks_fts` on every `legal_chunks` insert:
```sql
CREATE TRIGGER chunks_fts_insert AFTER INSERT ON legal_chunks BEGIN
    INSERT INTO chunks_fts(chunk_id, content, article_title, article_uuid, so_ky_hieu)
    VALUES (new.chunk_id, new.content, (SELECT article_title FROM legal_articles WHERE article_uuid=new.article_uuid), new.article_uuid, new.so_ky_hieu);
END;
```

---

### D6 — RRF Merge Strategy (REVISED)

**Decision**: **RRF at chunk level → group by article after merge**.

**❌ Old**: Deduplicate by `article_uuid` during RRF → loses granularity when multiple chunks from same article rank well.

**✅ New pipeline**:
```
Vector hits  (chunk_ids + scores)
FTS hits     (chunk_ids + ranks)
     ↓
RRF merge at chunk level:
    scores[chunk_id] += 1 / (k + rank_i)   for each source i
     ↓
Top-50 chunks by RRF score
     ↓
[Reranker — see D7]
     ↓
Top-10 chunks
     ↓
Group by article_uuid:
    articles[uuid] = max(chunk_score) over all matched chunks
     ↓
Top-N unique articles (N = 5 default)
     ↓
Expand sibling clauses (D8)
```

```python
# RRF merge
k = 60
scores: dict[str, float] = {}
for rank, chunk_id in enumerate(vector_hits):
    scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)
for rank, chunk_id in enumerate(fts_hits):
    scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)

# Sort → top-50 chunks
top_chunks = sorted(scores.items(), key=lambda x: -x[1])[:50]

# After rerank → group by article
articles: dict[str, float] = {}
for chunk_id, score in reranked_top10:
    article_uuid = chunk_to_article[chunk_id]
    articles[article_uuid] = max(articles.get(article_uuid, 0), score)
```

---

### D7 — Reranker (NEW)

**Decision**: **BAAI/bge-reranker-v2-m3** (multilingual cross-encoder).

- Multilingual, strong Vietnamese support
- Better than `ms-marco-MiniLM-L-6-v2` for Vietnamese
- No API key needed (local model)

**Pipeline position**: After RRF top-50 chunks, before group-by-article.

**Latency note**: Model is ~550MB. Consider loading at startup, not per-request. For production, `top-30` instead of top-50 into reranker.

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")  # load once at startup

def rerank_chunks(query: str, chunks: list[dict], top_k: int = 10) -> list[dict]:
    pairs = [(query, chunk["content"]) for chunk in chunks]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(chunks, scores), key=lambda x: -x[1])
    return [c for c, _ in ranked[:top_k]]
```

**Input**: Top-50 chunks from RRF (with content fetched from `legal_chunks`)
**Output**: Top-10 chunks for group-by-article step.

---

### D8 — Context Expansion (NEW — sibling clauses only)

**Decision**: After selecting top-N articles, expand each with sibling clauses from same Điều.

**Scope**: Sibling clauses only. Referenced articles ("theo Điều X") deferred to Phase 11.

```python
def expand_article_context(article_uuid: str, matched_chunk_ids: list[str]) -> list[str]:
    """Return all chunks from same article to provide full clause context."""
    sibling_chunks = db.execute(
        "SELECT content FROM legal_chunks WHERE article_uuid = ? ORDER BY id",
        (article_uuid,)
    ).fetchall()
    return [row["content"] for row in sibling_chunks]
```

Response payload includes:
- `full_content` (full Điều from `legal_articles`)
- `matched_chunks` (which chunks triggered the match)
- `all_sibling_chunks` (optional — for UI clause highlighting)

---

## Retrieval Flow (Locked — 11-step)

```
1.  User query (natural language)
2.  Embed query → dense vector (SBERT)
3.  Qdrant vector search → top-50 chunk_ids
4.  FTS5 keyword search on chunks_fts → top-50 chunk_ids
5.  RRF merge at chunk level → top-50 chunks ranked
6.  Fetch chunk content from legal_chunks (for reranker input)
7.  Rerank top-50 with BAAI/bge-reranker-v2-m3 → top-10 chunks
8.  Group by article_uuid → top-5 unique articles (max score wins)
9.  Expand sibling clauses: SELECT * FROM legal_chunks WHERE article_uuid = ?
10. Fetch full article: SELECT * FROM legal_articles WHERE article_uuid IN (...)
11. Return: so_ky_hieu + article_title + full_content + matched_chunks + rrf_score
```

---

## Implementation Scope (for Planner)

### Files to modify:

**Indexer side:**
- **`db/sqlite.py`** — New schema: `legal_articles` + `legal_chunks` + `chunks_fts` + triggers
- **`indexer.py`** — Replace `collect_chunks` with:
  1. Walk parser tree → collect all ARTICLE (Điều) nodes
  2. For each Điều: generate `article_uuid`, flatten `full_content`
  3. For each Điều: call `split_article()` → list of chunks
  4. For each chunk: generate `chunk_id`, build `enriched` text (breadcrumb + text)
  5. Embed `enriched` → Qdrant upsert (minimal payload)
  6. Insert into `legal_articles` + `legal_chunks` + `chunks_fts` atomically

**Retrieval side:**
- **`core/retriever.py`** — Implement 11-step pipeline: vector + FTS → RRF (chunk-level) → rerank → group → expand
- **`api/`** routes — Return `full_content` + `article_title` + `so_ky_hieu` + matched chunks

### New dependencies:
```txt
sentence-transformers>=2.7.0   # already present for bi-encoder
# BAAI/bge-reranker-v2-m3 is loaded via CrossEncoder — same package
```

### New env config:
```env
MIN_CHUNK_CHARS=50
MAX_EMBED_CHARS=500
CHUNK_OVERLAP=100
MAX_CHUNKS_PER_ARTICLE=20
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_N=10
RERANKER_INPUT_SIZE=30         # top-30 chunks from RRF fed into reranker
RETRIEVAL_TOP_K=5              # top-5 articles returned
```

---

## Canonical Refs

- `indexer.py` — current ingestion pipeline to be refactored (line 210: existing RecursiveCharacterTextSplitter reuse)
- `db/sqlite.py` — DB schema, `init_db`, FTS5 setup
- `core/parser.py` — `VietnameseLegalParser`, `LegalNode`, `LegalLevel` enum
- `core/retriever.py` / `rag_pipeline.py` — RRF merge code (lines 80–107)
- `.planning/phases/02-full-scale-indexing/02-CONTEXT.md` — prior batching & indexing decisions
- `.planning/phases/05-hierarchical-structural-chunking/` — original hierarchical chunking rationale

---

## Corrections Log

| # | Original Error | Correct Behavior |
|---|---------------|------------------|
| 1 | CONTEXT said "merge upward" for short chunks | **Skip** creating separate chunk — content already in `full_content`. *(Superseded by D1 revision below)* |
| 2 | Retrieval flow only used Qdrant vector search | **Hybrid search** required: Qdrant vector + FTS5 keyword → RRF merge. |
| 3 | Truncate enriched text to `MAX_EMBED_CHARS=800` | **❌ WRONG** — loses 70–80% of long Điều. Correct: **split into multiple chunks**, each embedded separately (see D1). |
| 4 | Short chunk `< 30 chars` → skip | **❌ WRONG** — "cấm", "phạt tiền" are legally critical. Correct: **merge into parent buffer** so signal is preserved in the chunk (see D1, D5-short-chunk). |
| 5 | FTS5 on `legal_articles.full_content` | **Changed to `chunks_fts`** on `legal_chunks.content` — same granularity as vector, cleaner RRF alignment (see D5). |
| 6 | RRF deduplication by `article_uuid` | **Changed to RRF at chunk level** → group by article after rerank (see D6). |
| 7 | `split_article()` trailing buffer data leak | **🐞 Edge case**: nếu Khoản/Điểm **cuối cùng** của Điều có `len < MIN_CHUNK_CHARS`, nó được cộng vào `parent_buffer` rồi vòng lặp kết thúc — buffer không bao giờ được flush → dữ liệu bốc hơi khỏi Qdrant + `legal_chunks`. **Fix**: thêm post-loop flush `if parent_buffer: chunks.append(...)` sau vòng `for clause` (đã áp dụng trong D1). |

---

## Deferred Ideas

- **Referenced article expansion**: Parse "theo Điều X" references → lookup + return → defer to Phase 11
- **Graph traversal**: Cross-document legal linking → future phase
- **A/B test collection**: Compare v1 vs v2 chunk strategy on eval set → Phase 6-style eval
- **Streaming re-index**: Resume-from-checkpoint via `indexing_status` → can add alongside rebuild

---

*Decisions locked: 2026-04-29 (refined)*
*Status: Ready for planning*
