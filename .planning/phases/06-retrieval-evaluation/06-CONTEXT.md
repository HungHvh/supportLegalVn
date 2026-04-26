# Phase 6: Retrieval Evaluation

## Objective
The goal of this phase is to quantitatively and qualitatively evaluate the improvements brought by **Hierarchical Structural Chunking** and **Hybrid Search** (Phase 5) compared to the initial baseline (Phase 2).

## Success Criteria
- **Hit Rate @ 3**: Increase by at least 20% for complex legal queries.
- **MRR (Mean Reciprocal Rank)**: Improvement over the baseline.
- **Faithfulness (Ragas)**: Verify that context injection reduces hallucinations in generation.

## Technical Strategy
1.  **Synthetic Dataset Generation**: Use Gemini to generate a "Golden Dataset" of 20-30 query-context pairs from sample Vietnamese laws.
2.  **Comparative Benchmarking**:
    *   **A: Baseline** - Fixed-size chunking + Dense-only search.
    *   **B: Improved** - Hierarchical chunking + Context Injection + Hybrid Search (Dense + Sparse).
3.  **Metrics Selection**:
    *   Retrieval: Hit Rate, MRR, NDCG.
    *   Generation: Faithfulness, Answer Relevance (using Ragas library).

## Assumptions
- We can use a subset of the dataset (100-200 documents) for evaluation to save time/cost.
- `ragas` library is compatible with the environment or can be simulated with custom Gemini-based scorers.

## Open Questions
- Do we have a specific set of "edge case" laws (e.g., laws with many exceptions) to prioritize in evaluation?
- Should we evaluate the impact of **RRF (Reciprocal Rank Fusion)** weights specifically?
