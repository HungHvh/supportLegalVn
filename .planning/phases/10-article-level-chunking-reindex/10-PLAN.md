# Phase 10: Article-Level Chunking & Full Re-index

## Goal

Refactor toàn bộ indexing và retrieval pipeline theo kiến trúc mới:
- **Embed**: Khoản-level chunks (split bằng hybrid structural + RecursiveTextSplitter, không truncate)
- **Store**: Full Điều text trong `legal_articles`, chunks trong `legal_chunks`
- **Retrieve**: Vector + FTS5 (chunk-level) → RRF → Rerank (BAAI cross-encoder) → Group → Expand siblings

---

## Architecture (11-step pipeline)

```
INDEXING:
  Parser → ARTICLE nodes
       └─→ legal_articles (full_content = flattened all Khoản)
       └─→ split_article() → N chunks per Điều
               └─→ Qdrant (enriched vector) + legal_chunks (raw) + chunks_fts

RETRIEVAL:
  query → embed → Qdrant top-50 chunks
               → chunks_fts top-50 chunks
  → RRF (chunk-level) → top-50
  → BAAI/bge-reranker-v2-m3 → top-10
  → group by article_uuid → top-5 articles
  → expand sibling clauses
  → return full_content + matched_chunks
```

---

## Plan 10-01: Schema & DB Refactor (`db/sqlite.py`)

**Wave**: 1 (no dependencies)
**Files**: `db/sqlite.py`

### Read first
- `db/sqlite.py` — current `init_db`, FTS5 setup, trigger patterns

### Action

**Drop old schema**:
```sql
DROP TABLE IF EXISTS legal_documents;
DROP VIRTUAL TABLE IF EXISTS docs_fts;
DROP TABLE IF EXISTS indexing_status;
DROP TRIGGER IF EXISTS legal_documents_ai;
DROP TRIGGER IF EXISTS legal_documents_ad;
DROP TRIGGER IF EXISTS legal_documents_au;
```

**Create `legal_articles`**:
```sql
CREATE TABLE IF NOT EXISTS legal_articles (
    article_uuid  TEXT PRIMARY KEY,
    doc_id        TEXT NOT NULL,
    so_ky_hieu    TEXT,
    article_title TEXT,
    article_path  TEXT,
    full_content  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_la_doc_id ON legal_articles(doc_id);
```

**Create `legal_chunks`**:
```sql
CREATE TABLE IF NOT EXISTS legal_chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id     TEXT UNIQUE NOT NULL,
    article_uuid TEXT NOT NULL REFERENCES legal_articles(article_uuid),
    doc_id       TEXT NOT NULL,
    so_ky_hieu   TEXT,
    level        TEXT,        -- "KHOẢN" | "ĐIỂM" | "ARTICLE"
    chunk_path   TEXT,
    content      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lc_article_uuid ON legal_chunks(article_uuid);
CREATE INDEX IF NOT EXISTS idx_lc_doc_id ON legal_chunks(doc_id);
```

**Create `chunks_fts`** (D5 — FTS on chunks, NOT on full article):
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id     UNINDEXED,
    content,
    article_title,
    article_uuid UNINDEXED,
    so_ky_hieu   UNINDEXED,
    tokenize='unicode61 remove_diacritics 0'
);
```

**Create insert trigger** (auto-populate FTS on insert):
```sql
CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON legal_chunks BEGIN
    INSERT INTO chunks_fts(chunk_id, content, article_title, article_uuid, so_ky_hieu)
    VALUES (
        new.chunk_id,
        new.content,
        (SELECT article_title FROM legal_articles WHERE article_uuid = new.article_uuid),
        new.article_uuid,
        new.so_ky_hieu
    );
END;
```

**Create `indexing_status`** (idempotency — keep for resume):
```sql
CREATE TABLE IF NOT EXISTS indexing_status (
    doc_id       TEXT PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Acceptance Criteria
- `PRAGMA table_info(legal_articles)` → 6 columns: `article_uuid, doc_id, so_ky_hieu, article_title, article_path, full_content`
- `PRAGMA table_info(legal_chunks)` → 8 columns: `id, chunk_id, article_uuid, doc_id, so_ky_hieu, level, chunk_path, content`
- `SELECT name FROM sqlite_master WHERE type='table'` → contains `legal_articles`, `legal_chunks`, `indexing_status`
- `SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'` → 1 row
- `SELECT name FROM sqlite_master WHERE type='trigger'` → contains `chunks_fts_insert`
- `python db/sqlite.py` exits 0

---

## Plan 10-02: Indexer Refactor (`indexer.py`)

**Wave**: 2 (depends on 10-01)
**Files**: `indexer.py`

### Read first
- `indexer.py` — current `collect_chunks`, `process_batch`, splitter config (line ~210)
- `core/parser.py` — `LegalNode`, `LegalLevel`, `full_path`, `children`, `content`
- `db/sqlite.py` — new `init_db` from Plan 10-01

### Action

**1. Keep `RecursiveCharacterTextSplitter`** (reuse existing, tune config):
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""]
)
```

**2. New constants** (replace old `MAX_EMBED_CHARS=800`):
```python
MIN_CHUNK_CHARS = 50         # short clauses merge into parent buffer
MAX_EMBED_CHARS = 500        # target chunk size
CHUNK_OVERLAP   = 100
MAX_CHUNKS_PER_ARTICLE = 20  # soft cap — log warning, never hard drop
```

**3. New helper `flatten_article_content(node: LegalNode) -> str`**:
```python
def flatten_article_content(node: LegalNode) -> str:
    """Recursively concat toàn bộ text của Điều và các Khoản/Điểm con."""
    parts = []
    if node.content and node.content.strip():
        parts.append(node.content.strip())
    for child in node.children:
        if child.title:
            parts.append(child.title)
        parts.append(flatten_article_content(child))
    return "\n".join(p for p in parts if p)
```

**4. New helper `split_article(article_node: LegalNode) -> list[dict]`** (D1 + D1-bugfix):
```python
def split_article(article_node: LegalNode) -> list[dict]:
    """
    Hybrid split: structural Khoản boundaries first,
    RecursiveCharacterTextSplitter as fallback for long clauses.
    Short clauses (< MIN_CHUNK_CHARS) merge into parent buffer.
    POST-LOOP FLUSH prevents trailing buffer data leak (Correction #7).
    """
    chunks = []
    parent_buffer = ""

    for clause in article_node.children:
        text = clause.content.strip() if clause.content else ""

        # Short clause → accumulate in buffer, never skip
        if len(text) < MIN_CHUNK_CHARS:
            parent_buffer += " " + text
            continue

        # Flush buffer into current clause
        if parent_buffer:
            text = parent_buffer.strip() + " " + text
            parent_buffer = ""

        # Long clause → split further
        if len(text) > MAX_EMBED_CHARS:
            sub_texts = recursive_splitter.split_text(text)
        else:
            sub_texts = [text]

        for sub in sub_texts:
            chunks.append({
                "path": clause.full_path,
                "text": sub,
                "level": clause.level.name if clause.level else "KHOẢN",
            })

    # ⚠️ POST-LOOP FLUSH (Correction #7): flush remaining buffer
    # Prevents data leak when last clause(s) are all < MIN_CHUNK_CHARS
    if parent_buffer:
        chunks.append({
            "path": article_node.full_path,
            "text": parent_buffer.strip(),
            "level": "KHOẢN",
        })

    # Fallback: no clause children → split full_content directly
    if not chunks:
        for sub in recursive_splitter.split_text(article_node.full_content):
            chunks.append({
                "path": article_node.full_path,
                "text": sub,
                "level": "ARTICLE",
            })

    # Soft cap: log warning if exceeded (never drop)
    if len(chunks) > MAX_CHUNKS_PER_ARTICLE:
        logger.warning(
            f"Article {article_node.full_path} produced {len(chunks)} chunks "
            f"(soft cap={MAX_CHUNKS_PER_ARTICLE})"
        )

    return chunks
```

**5. New collector `collect_article_chunks(root, doc_id, so_ky_hieu)`**:
```python
def collect_article_chunks(root: LegalNode, doc_id: str, so_ky_hieu: str):
    articles_batch: list[dict] = []
    chunks_batch:   list[dict] = []

    article_nodes = [n for n in walk_tree(root) if n.level == LegalLevel.ARTICLE]

    for article_node in article_nodes:
        article_uuid  = str(uuid.uuid4())
        full_content  = flatten_article_content(article_node)
        article_title = article_node.title or so_ky_hieu

        articles_batch.append({
            "article_uuid":  article_uuid,
            "doc_id":        doc_id,
            "so_ky_hieu":    so_ky_hieu,
            "article_title": article_title,
            "article_path":  article_node.full_path,
            "full_content":  full_content,   # NOT truncated in SQLite
        })

        raw_chunks = split_article(article_node)
        for c in raw_chunks:
            chunk_id = str(uuid.uuid4())
            enriched = f"[{c['path']}] {c['text']}"  # embedded, not stored
            chunks_batch.append({
                "chunk_id":      chunk_id,
                "article_uuid":  article_uuid,
                "doc_id":        doc_id,
                "so_ky_hieu":    so_ky_hieu,
                "level":         c["level"],
                "chunk_path":    c["path"],
                "content":       c["text"],        # raw text, stored in SQLite
                "enriched_text": enriched,         # used for embedding only
                "article_title": article_title,    # denorm for Qdrant payload
            })

    # Fallback: document has no ARTICLE nodes
    if not article_nodes:
        article_uuid = str(uuid.uuid4())
        raw_text = getattr(root, "full_content", "") or ""
        articles_batch.append({
            "article_uuid":  article_uuid,
            "doc_id":        doc_id,
            "so_ky_hieu":    so_ky_hieu,
            "article_title": so_ky_hieu,
            "article_path":  so_ky_hieu,
            "full_content":  raw_text,
        })
        for sub in recursive_splitter.split_text(raw_text):
            chunk_id = str(uuid.uuid4())
            chunks_batch.append({
                "chunk_id":      chunk_id,
                "article_uuid":  article_uuid,
                "doc_id":        doc_id,
                "so_ky_hieu":    so_ky_hieu,
                "level":         "ARTICLE",
                "chunk_path":    so_ky_hieu,
                "content":       sub,
                "enriched_text": f"[{so_ky_hieu}] {sub}",
                "article_title": so_ky_hieu,
            })

    return articles_batch, chunks_batch
```

**6. Update `process_batch`** — embed chunks, insert to 2 tables:
```python
async def process_batch(articles, chunks, doc_ids, embed_provider, q_mgr, db_conn, use_sparse=True):
    # Embed only chunks (not articles)
    texts = [c["enriched_text"] for c in chunks]
    vectors = await embed_provider.embed_batch(texts, use_sparse=use_sparse)

    # Qdrant upsert — minimal payload
    points = [
        models.PointStruct(
            id=c["chunk_id"],
            vector={"dense": v["dense"], "sparse": v.get("sparse", [])},
            payload={
                "chunk_id":      c["chunk_id"],
                "article_uuid":  c["article_uuid"],
                "doc_id":        c["doc_id"],
                "so_ky_hieu":    c["so_ky_hieu"],
                "level":         c["level"],
                "article_title": c["article_title"],
            }
        )
        for c, v in zip(chunks, vectors)
    ]
    q_mgr.upsert(points)

    # SQLite: articles first (FK), then chunks (trigger auto-populates chunks_fts)
    cursor = db_conn.cursor()
    cursor.executemany(
        "INSERT OR IGNORE INTO legal_articles "
        "(article_uuid, doc_id, so_ky_hieu, article_title, article_path, full_content) "
        "VALUES (?,?,?,?,?,?)",
        [(a["article_uuid"], a["doc_id"], a["so_ky_hieu"],
          a["article_title"], a["article_path"], a["full_content"])
         for a in articles]
    )
    cursor.executemany(
        "INSERT OR IGNORE INTO legal_chunks "
        "(chunk_id, article_uuid, doc_id, so_ky_hieu, level, chunk_path, content) "
        "VALUES (?,?,?,?,?,?,?)",
        [(c["chunk_id"], c["article_uuid"], c["doc_id"], c["so_ky_hieu"],
          c["level"], c["chunk_path"], c["content"])
         for c in chunks]
    )
    cursor.executemany(
        "INSERT OR IGNORE INTO indexing_status (doc_id) VALUES (?)",
        [(d,) for d in doc_ids]
    )
    db_conn.commit()
```

**7. Update `.env.example`**:
```env
MIN_CHUNK_CHARS=50
MAX_EMBED_CHARS=500
CHUNK_OVERLAP=100
MAX_CHUNKS_PER_ARTICLE=20
BATCH_SIZE=512
USE_SPARSE_EMBEDDING=true
```

### Acceptance Criteria
- `python indexer.py --limit 100` (hoặc temp cap trong code) exits 0
- `SELECT COUNT(*) FROM legal_articles` > 0
- `SELECT AVG(LENGTH(full_content)) FROM legal_articles` > 400 (không bị truncate)
- `SELECT COUNT(*) FROM legal_chunks` >= `(SELECT COUNT(*) FROM legal_articles)` (≥ 1 chunk per article)
- `SELECT COUNT(*) FROM chunks_fts` = `SELECT COUNT(*) FROM legal_chunks` (trigger hoạt động)
- Qdrant: tất cả points có payload key `article_uuid` (không null)
- `SELECT COUNT(*) FROM legal_chunks WHERE LENGTH(content) < 50 AND level != 'ARTICLE'` = 0 (không có orphan short chunk)
- Log không có `split_article()` panic hay silent empty chunks

---

## Plan 10-03: Retriever Refactor (`core/retriever.py`)

**Wave**: 2 (depends on 10-01; parallel với 10-02 về schema — nhưng nên sau 10-02 về test)
**Files**: `core/retriever.py` (hoặc `rag/pipeline.py` — xác nhận tên file thực tế)

### Read first
- `core/retriever.py` — current hybrid search, RRF merge (lines 80–107), Qdrant client usage
- `db/sqlite.py` — new schema từ 10-01
- `.env.example` — new env vars từ 10-02

### Action

**1. Add reranker** (load once at module level, D7):
```python
import os
from sentence_transformers import CrossEncoder

RERANKER_MODEL    = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANKER_TOP_N    = int(os.getenv("RERANKER_TOP_N", "10"))
RERANKER_INPUT_N  = int(os.getenv("RERANKER_INPUT_SIZE", "30"))
RETRIEVAL_TOP_K   = int(os.getenv("RETRIEVAL_TOP_K", "5"))

_reranker: CrossEncoder | None = None

def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANKER_MODEL)
    return _reranker
```

**2. Replace retrieval method** — full 11-step pipeline:
```python
async def hybrid_retrieve(query: str, db_conn, q_client, embed_fn) -> list[dict]:
    K = 50  # candidates from each source

    # Step 2-3: Vector search on chunks
    query_vec = await embed_fn(query)
    qdrant_hits = q_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vec,
        limit=K,
        with_payload=True
    )
    # chunk_id → rank
    vector_chunk_ids = [hit.payload["chunk_id"] for hit in qdrant_hits]

    # Step 4: FTS5 search on chunks_fts (D5)
    cursor = db_conn.cursor()
    cursor.execute(
        "SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
        (query, K)
    )
    fts_chunk_ids = [row["chunk_id"] for row in cursor.fetchall()]

    # Step 5: RRF merge at chunk level (D6 — NOT article level)
    RRF_K = 60
    scores: dict[str, float] = {}
    for rank, cid in enumerate(vector_chunk_ids):
        scores[cid] = scores.get(cid, 0) + 1 / (RRF_K + rank)
    for rank, cid in enumerate(fts_chunk_ids):
        scores[cid] = scores.get(cid, 0) + 1 / (RRF_K + rank)

    top_chunk_ids = sorted(scores, key=scores.__getitem__, reverse=True)[:RERANKER_INPUT_N]

    # Step 6: Fetch chunk content for reranker
    if not top_chunk_ids:
        return []
    placeholders = ",".join("?" * len(top_chunk_ids))
    cursor.execute(
        f"SELECT chunk_id, content, article_uuid FROM legal_chunks "
        f"WHERE chunk_id IN ({placeholders})",
        top_chunk_ids
    )
    chunk_rows = {row["chunk_id"]: row for row in cursor.fetchall()}
    top_chunks = [
        {"chunk_id": cid, "content": chunk_rows[cid]["content"],
         "article_uuid": chunk_rows[cid]["article_uuid"], "rrf_score": scores[cid]}
        for cid in top_chunk_ids if cid in chunk_rows
    ]

    # Step 7: Rerank with BAAI/bge-reranker-v2-m3 (D7)
    reranker = get_reranker()
    pairs = [(query, c["content"]) for c in top_chunks]
    rerank_scores = reranker.predict(pairs)
    ranked = sorted(zip(top_chunks, rerank_scores), key=lambda x: -x[1])
    top10_chunks = [c for c, _ in ranked[:RERANKER_TOP_N]]

    # Step 8: Group by article_uuid → top-K unique articles (D6)
    article_scores: dict[str, float] = {}
    article_matched_chunks: dict[str, list] = {}
    for c, score in zip(top10_chunks, [s for _, s in ranked[:RERANKER_TOP_N]]):
        uuid = c["article_uuid"]
        if score > article_scores.get(uuid, -1):
            article_scores[uuid] = score
        article_matched_chunks.setdefault(uuid, []).append(c["chunk_id"])

    top_article_uuids = sorted(article_scores, key=article_scores.__getitem__, reverse=True)[:RETRIEVAL_TOP_K]

    # Step 9-10: Expand siblings + fetch full articles (D8)
    results = []
    for uuid in top_article_uuids:
        cursor.execute(
            "SELECT article_uuid, so_ky_hieu, article_title, full_content "
            "FROM legal_articles WHERE article_uuid = ?",
            (uuid,)
        )
        article = cursor.fetchone()
        if not article:
            continue

        # Sibling clauses for context expansion
        cursor.execute(
            "SELECT chunk_id, content FROM legal_chunks WHERE article_uuid = ? ORDER BY id",
            (uuid,)
        )
        sibling_chunks = [{"chunk_id": r["chunk_id"], "content": r["content"]}
                          for r in cursor.fetchall()]

        results.append({
            "article_uuid":    uuid,
            "so_ky_hieu":      article["so_ky_hieu"],
            "article_title":   article["article_title"],
            "full_content":    article["full_content"],
            "rerank_score":    article_scores[uuid],
            "matched_chunk_ids": article_matched_chunks[uuid],
            "sibling_chunks":  sibling_chunks,   # Step 11 — for UI clause highlighting
        })

    return results
```

**3. Update API response schema** — routes trả về `full_content + matched_chunk_ids`:
```python
# In api/ handler:
return {
    "results": [
        {
            "so_ky_hieu":       r["so_ky_hieu"],
            "article_title":    r["article_title"],
            "full_content":     r["full_content"],
            "rerank_score":     r["rerank_score"],
            "matched_chunk_ids": r["matched_chunk_ids"],
        }
        for r in results
    ]
}
```

### Acceptance Criteria
- Query `"xử phạt vi phạm"` → response `results[0].full_content` length ≥ 200 chars
- `results[0].article_title` matches pattern `"Điều \d+\..*"` hoặc contains `so_ky_hieu`
- `results[0].matched_chunk_ids` is non-empty list
- `results[0].rerank_score` > 0
- FTS path hoạt động: `SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH 'xử phạt'` → ≥ 1 row
- Không có kết quả nào có `full_content` bị cắt giữa câu (kiểm tra ký tự cuối không phải `...` hay EOL cắt đột ngột)
- Reranker load không lỗi: `from sentence_transformers import CrossEncoder; CrossEncoder("BAAI/bge-reranker-v2-m3")` exits OK
- `len(results)` ≤ `RETRIEVAL_TOP_K (5)`

---

## Plan 10-04: Full Re-index (Execution)

**Wave**: 3 (depends on 10-01 + 10-02)
**Files**: Không sửa code — chỉ chạy lệnh

### Read first
- `indexer.py` — sau khi đã refactor ở 10-02

### Action

```bash
# 1. Drop & re-init DB (D3 — clean slate)
python -c "from db.sqlite import init_db; init_db(drop_existing=True)"

# 2. Drop Qdrant collection
python -c "
from core.qdrant_manager import QdrantManager
qm = QdrantManager()
qm.delete_collection()
qm.create_collection()
"

# 3. Run full re-index
python indexer.py
```

### Acceptance Criteria
- `SELECT COUNT(*) FROM legal_articles` ≥ 50000 (sau khi chạy xong)
- `SELECT COUNT(*) FROM legal_chunks` ≥ `(SELECT COUNT(*) FROM legal_articles)` × 1.5 (avg > 1 chunk per article)
- `SELECT COUNT(*) FROM chunks_fts` = `SELECT COUNT(*) FROM legal_chunks`
- Qdrant collection point count ≥ `SELECT COUNT(*) FROM legal_chunks`
- `SELECT COUNT(*) FROM indexing_status` = số doc đã index
- `SELECT MAX(LENGTH(full_content)) FROM legal_articles` > 1000 (có Điều dài không bị truncate)

---

## Plan 10-05: Smoke Test & Validation

**Wave**: 4 (depends on all above)

### Read first
- `scripts/run_benchmarks.py` — existing eval harness
- `.planning/phases/06-retrieval-evaluation/golden_set_synthetic.json` — golden queries

### Action

Chạy smoke test trên golden set:
```python
# Quick validation (first 20 queries from golden set)
from pathlib import Path
import json, asyncio

golden = json.loads(Path(".planning/phases/06-retrieval-evaluation/golden_set_synthetic.json").read_text())
queries = golden[:20]

results = asyncio.run(batch_retrieve([q["query"] for q in queries]))

for q, r in zip(queries, results):
    assert len(r) > 0, f"No results for: {q['query']}"
    assert r[0]["full_content"], f"Empty full_content for: {q['query']}"
    assert r[0]["rerank_score"] > 0, f"Zero rerank score for: {q['query']}"
    print(f"✓ {q['query'][:50]} → {r[0]['article_title'][:40]} (score={r[0]['rerank_score']:.3f})")
```

### Acceptance Criteria
- ≥ 18/20 golden queries trả về kết quả không rỗng (≥ 90% recall@1)
- Không có `full_content` nào < 100 chars (không phải fragment)
- Avg `rerank_score` > 0.5 trên 20 queries
- Không có Python exception trong quá trình chạy

---

## Acceptance Criteria (Overall)

- [ ] `chunks_fts` có cùng row count với `legal_chunks` (trigger hoạt động đúng)
- [ ] `legal_articles.full_content` avg length ≥ 400 chars (không bị truncate)
- [ ] Mỗi `legal_chunks` record có `article_uuid` hợp lệ (FK constraint không lỗi)
- [ ] Qdrant payload của mọi point có key `chunk_id`, `article_uuid`, `so_ky_hieu`
- [ ] `split_article()` trailing buffer flush hoạt động: Điều có khoản cuối < 50 chars → chunk vẫn tồn tại trong `legal_chunks`
- [ ] Reranker load OK và trả về `float` score cho mỗi pair
- [ ] Golden set smoke test: ≥ 90% recall@1
- [ ] `MAX_CHUNKS_PER_ARTICLE=20` warning log xuất hiện khi vượt (không exception)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `split_article()` trailing buffer data leak | **Fixed** (Correction #7): post-loop flush sau `for clause` |
| Reranker latency (~550MB model) | Load at startup (`get_reranker()` singleton), không load per-request |
| FTS trigger slow trên bulk insert | Disable trigger trước bulk insert, sau đó `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')` |
| Parser không detect ARTICLE nodes | Fallback: full doc = 1 article, split bằng `recursive_splitter` |
| Khoản cuối ngắn bị mất | Fixed bởi post-loop buffer flush |
| `RERANKER_INPUT_SIZE=30` quá nhỏ | Có thể tăng lên 50 nếu latency cho phép — tunable qua env |
| Re-index 518K docs tốn thời gian | `indexing_status` table cho phép resume — không drop nó |

---

## Dependencies

- Phase 2 (Indexer infrastructure)
- Phase 5 (VietnameseLegalParser — `LegalLevel.ARTICLE`, `full_path`, `children`)

---

*Rewritten: 2026-04-29 — Aligned with CONTEXT.md D1–D8 (hybrid chunking, chunks_fts, chunk-level RRF, BAAI reranker, sibling expansion, trailing-buffer fix)*
*Status: Ready for execution*
