# Phase 5: Hierarchical Structural Chunking

## 1. Objective
Replace the generic `MarkdownHeaderTextSplitter` and `RecursiveCharacterTextSplitter` with a specialized Vietnamese Legal Parser. This ensures that legal documents are split at logical boundaries (Điều, Khoản, Điểm) and that every chunk inherits its hierarchical context (Part > Chapter > Section > Article).

## 2. Context & Rationale
Văn bản pháp luật Việt Nam có tính phân cấp cực kỳ rõ ràng. Việc sử dụng fixed-size chunking (ví dụ: 1000 tokens) mang lại rủi ro lớn:
- **Mất bối cảnh**: Một Điều luật có thể bị cắt đôi, làm mất đi các ngoại lệ ở Khoản sau.
- **Nhiễu thông tin**: Một chunk chứa nửa cuối của Điều này và nửa đầu của Điều kia.

## 3. Implementation Decisions

### 3.1 Data Extraction & Parsing (Hybrid Pipeline)
- **Step 1: Layout & OCR**: Use specialized libraries (`marker-pdf`, `unstructured.io`, or `LlamaParse`) to convert raw PDF/Scan/Messy text into clean, structural Markdown. This step handles OCR, table extraction, and header/footer removal.
- **Step 2: Semantic Regex**: Apply custom Regex (e.g., `^Điều \d+\.`, `^Chương [IXV]+`) on the *cleaned* Markdown from Step 1 to identify the legal hierarchy.

### 3.2 Context Injection (Document Enrichment)
- **Mandatory Technique**: Every chunk must be prefixed with a hierarchical header before embedding and indexing.
- **Format**: `[Law Name > Chapter > Article > Clause] \n [Chunk Content]`
- **Goal**: Improve semantic retrieval (vector space) and keyword matching (FTS/BM25) by making the context explicit in the indexed text.

### 3.3 Metadata Schema
- **Redundancy**: Hierarchical info must be stored BOTH inside the chunk text (for search) and in the Payload (for hard filtering).
- **Fields**: `law_id`, `law_name`, `year`, `chapter`, `article`, `clause`, `full_path`.

## 4. Technical Constraints
- Must handle 3.6GB dataset efficiently (streaming).
- Must maintain compatibility with existing Qdrant/SQLite schema (or extend it).
- Vietnamese language nuances in numbering and formatting.

## 5. Success Criteria
- [ ] Precision improvement in retrieval for specific clauses.
- [ ] No more "broken" articles in chunks.
- [ ] Metadata correctly reflects the hierarchy path.
