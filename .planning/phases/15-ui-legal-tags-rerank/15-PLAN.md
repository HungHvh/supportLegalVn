---
wave: 1
depends_on: []
files_modified:
  - core/rag_pipeline.py
  - frontend/src/components/MainPane.tsx
autonomous: true
---

# Phase 15: Cải thiện UI chuẩn ngành luật với Tag phân loại và Rerank

## Task 1: Rerank Legal Sources by Authority (Backend)

<read_first>
- core/rag_pipeline.py
</read_first>

<action>
Modify `acustom_query` in `core/rag_pipeline.py` to sort the retrieved `nodes` based on their legal authority BEFORE building the context string (`_build_context_str(nodes)`).

1. Add a helper function `_get_legal_priority(node)` inside or before `acustom_query`:
   - Returns 1 if `"QH"` is in `so_ky_hieu` (Luật, Nghị quyết Quốc hội).
   - Returns 2 if `"NĐ-CP"`, `"CP"`, or `"TT"` is in `so_ky_hieu` (Nghị định, Thông tư).
   - Returns 3 if `"UBND"` is in `so_ky_hieu` (Quyết định của địa phương).
   - Returns 2 for others (default fallback).

2. Sort `nodes` list using this priority as the primary key and the retrieval score as the secondary key (descending):
   `nodes.sort(key=lambda n: (_get_legal_priority(n), -float(n.score)))`

This ensures that the highest-authority documents (Luật) are always at the top of the LLM context and the citation list.
</action>

<acceptance_criteria>
- `core/rag_pipeline.py` contains the sorting logic inside `acustom_query`.
- `nodes.sort(key=lambda` is present and uses priority + score.
- The default priority for unmatched documents is handled safely without crashing.
</acceptance_criteria>

## Task 2: Add Legal Tag/Badge in UI (Frontend)

<read_first>
- frontend/src/components/MainPane.tsx
</read_first>

<action>
Modify `frontend/src/components/MainPane.tsx` to display color-coded badges for citations based on their source.

1. Add a helper function `getLegalTag(source: string)` that returns an object `{ label: string, colorClass: string }`:
   - If `source` includes `"QH"`: return `{ label: "Luật / Nghị quyết", colorClass: "bg-red-100 text-red-700 border-red-200" }`
   - If `source` includes `"NĐ-CP"` or `"CP"` or `"TT"`: return `{ label: "Văn bản hướng dẫn", colorClass: "bg-blue-100 text-blue-700 border-blue-200" }`
   - If `source` includes `"UBND"`: return `{ label: "Văn bản địa phương", colorClass: "bg-emerald-100 text-emerald-700 border-emerald-200" }`
   - Default: return `{ label: "Tài liệu", colorClass: "bg-zinc-100 text-zinc-700 border-zinc-200" }`

2. In the `MainPane` component, specifically inside the `citations.map` block (around line 203), call `getLegalTag(citation.source)`.
3. Display the returned badge immediately below the `<h3>` of the citation source or inline with it. Use standard Tailwind classes:
   `<span className={\`text-[10px] uppercase font-bold px-2 py-0.5 rounded border \${tag.colorClass}\`}>{tag.label}</span>`
</action>

<acceptance_criteria>
- `MainPane.tsx` contains the `getLegalTag` helper function.
- The badges use the exact specified text ("Luật / Nghị quyết", "Văn bản hướng dẫn", "Văn bản địa phương").
- Color classes map correctly to red, blue, and emerald backgrounds/texts.
</acceptance_criteria>

## Verification

- [ ] Backend sorting places `"QH"` items before `"CP"` items in `acustom_query`.
- [ ] Frontend citation list visually renders colored badges beneath each citation source title.

## Must Haves

- The LLM context must receive reranked nodes (QH first) so it prioritizes higher laws in its reasoning.
- The frontend must accurately map UI colors based on the document code without requiring additional backend API changes.
