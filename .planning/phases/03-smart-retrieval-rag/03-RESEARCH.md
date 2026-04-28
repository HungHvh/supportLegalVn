# Phase 3: Smart Retrieval & RAG - Research

**Date:** 2026-04-26
**Status:** Complete

## 1. LlamaIndex Custom Hybrid Retriever

To integrate our existing SQLite FTS5 and Qdrant storage into a unified LlamaIndex pipeline, we will implement a `CustomRetriever`.

### Implementation Pattern
```python
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import QueryBundle
from llama_index.core.schema import NodeWithScore

class LegalHybridRetriever(BaseRetriever):
    def __init__(self, vector_retriever, fts_retriever, rrf_k=60):
        self._vector_retriever = vector_retriever
        self._fts_retriever = fts_retriever
        self._rrf_k = rrf_k
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        # 1. Get results from both sources
        vector_nodes = self._vector_retriever.retrieve(query_bundle)
        fts_nodes = self._fts_retriever.retrieve(query_bundle)

        # 2. Apply Reciprocal Rank Fusion (RRF)
        combined_dict = {}
        
        def apply_rrf(nodes, weight=1.0):
            for rank, node in enumerate(nodes):
                node_id = node.node.node_id
                score = weight / (self._rrf_k + rank + 1)
                if node_id not in combined_dict:
                    combined_dict[node_id] = {"node": node, "score": 0.0}
                combined_dict[node_id]["score"] += score

        apply_rrf(vector_nodes, weight=0.5) # Weighting from CONTEXT.md
        apply_rrf(fts_nodes, weight=0.5)

        # 3. Sort and return top-K
        sorted_results = sorted(combined_dict.values(), key=lambda x: x["score"], reverse=True)
        return [NodeWithScore(node=res["node"].node, score=res["score"]) for res in sorted_results[:8]]
```

### Key Findings
- **Metadata Filters:** LlamaIndex's `QdrantVectorStore` supports `MetadataFilters` natively. We can pass a `FilterOperator.IN` list for multi-label domain filtering.
- **SQLite FTS5 Integration:** Since LlamaIndex doesn't have a native SQLite FTS5 retriever, we'll implement a simple one that queries the `chunks_fts` table and returns LlamaIndex `TextNode` objects.

## 2. Gemini Multi-label Classifier

### Prompt Strategy
The classifier will be a standalone step using `gemini-2.0-flash` with a Pydantic output model.

**Prompt Ingredients:**
- **Context:** List of 6 domains with definitions.
- **Output:** JSON matching `QueryClassification` schema.
- **Confidence:** Instruct the model to return `General` if no domain matches with >0.5 confidence.

## 3. Evaluation & Tracing (RAGAS + Phoenix)

### Arize Phoenix Instrumentation
Run locally via Docker or pip.
```python
import phoenix as px
import llama_index.core

px.launch_app()
llama_index.core.set_global_handler("arize_phoenix")
```

### RAGAS Metrics
- **Faithfulness:** Does the answer come from the retrieved chunks?
- **Answer Relevancy:** Does the answer address the user's specific legal question?
- **Context Precision:** Are the relevant chunks ranked highly?
- **Citation Check (Custom):** A regex-based post-processor to verify the "Theo Khoản X, Điều Y..." format.

## 4. IRAC Generation Prompt

**Structure:**
1. **Issue:** "Dựa trên câu hỏi của bạn về [vấn đề]..."
2. **Rule:** "Theo quy định tại [Trích dẫn cụ thể]..."
3. **Analysis:** "Điều này có nghĩa là [Giải thích chi tiết]..."
4. **Conclusion:** "Vì vậy, [Kết luận/Lời khuyên]..."
5. **Disclaimer:** "Lưu ý: Thông tin này chỉ mang tính tham khảo..."

## 5. Summary of Technical Requirements
- **LlamaIndex v0.10+** (Required for new API structure).
- **llama-index-llms-gemini** and **llama-index-embeddings-huggingface**.
- **Arize Phoenix** for tracing.
- **RAGAS** for metric calculation.
