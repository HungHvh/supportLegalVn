---
created: 2026-04-26T09:55:05+07:00
title: Implement Hierarchical Structural Chunking for Legal Documents
area: ingestion
files:
  - indexer.py:110-155
  - core/rag_pipeline.py
---

## Problem

The current chunking implementation uses `MarkdownHeaderTextSplitter` and `RecursiveCharacterTextSplitter`. This approach is risky for legal documents because:
1. **Context Fragmentation**: Fixed-size splitting (1000 tokens) can cut a law mid-sentence or separate a clause from its exceptions (e.g., Clause 3 referring back to Clause 1).
2. **Noise**: Mixing ends of one Article with the beginning of another in a single chunk reduces LLM focus.
3. **Format Dependency**: It relies on markdown headers (`#`, `##`), which may not exist or be inconsistent in raw legal text.

## Solution

Implement a specialized **Hierarchical Structural Chunking** strategy tailored for Vietnamese Law:
1. **Regex-based Parsing**: Identify structural markers:
   - `Phần` (Part)
   - `Chương` (Chapter)
   - `Mục` (Section)
   - `Điều` (Article) - `^Điều \d+\.`
   - `Khoản` (Clause) - `^\d+\.`
   - `Điểm` (Point) - `^[a-z]\)`
2. **Hierarchical Split**: Split documents down to the Article or Clause level.
3. **Metadata Inheritance**: Inject parent context (Law Name > Chapter > Article) into each chunk's metadata.
4. **Data Cleaning**: 
   - Normalize structural markers.
   - Clean up PDF artifacts (broken lines, headers/footers).
   - Maintain reading order.
