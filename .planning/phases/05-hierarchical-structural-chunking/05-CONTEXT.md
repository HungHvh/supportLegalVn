# Phase 5: Hierarchical Structural Chunking

## 1. Objective
Replace the generic `MarkdownHeaderTextSplitter` and `RecursiveCharacterTextSplitter` with a specialized Vietnamese Legal Parser. This ensures that legal documents are split at logical boundaries (Điều, Khoản, Điểm) and that every chunk inherits its hierarchical context (Part > Chapter > Section > Article).

## 2. Context & Rationale
Văn bản pháp luật Việt Nam có tính phân cấp cực kỳ rõ ràng. Việc sử dụng fixed-size chunking (ví dụ: 1000 tokens) mang lại rủi ro lớn:
- **Mất bối cảnh**: Một Điều luật có thể bị cắt đôi, làm mất đi các ngoại lệ ở Khoản sau.
- **Nhiễu thông tin**: Một chunk chứa nửa cuối của Điều này và nửa đầu của Điều kia.

## 3. Scope
- **Regex-based Parser**: Identify structural markers like `Phần`, `Chương`, `Mục`, `Điều`, `Khoản`, `Điểm`.
- **Metadata Inheritance**: Inject parent titles into the chunk payload.
- **Data Cleaning**: Normalize markers and clean PDF extraction artifacts.
- **Indexer Update**: Refactor `indexer.py` to use the new parser.

## 4. Technical Constraints
- Must handle 3.6GB dataset efficiently (streaming).
- Must maintain compatibility with existing Qdrant/SQLite schema (or extend it).
- Vietnamese language nuances in numbering and formatting.

## 5. Success Criteria
- [ ] Precision improvement in retrieval for specific clauses.
- [ ] No more "broken" articles in chunks.
- [ ] Metadata correctly reflects the hierarchy path.
