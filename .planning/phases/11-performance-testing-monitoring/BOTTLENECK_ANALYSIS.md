# Phase 11: Bottleneck Analysis

## Latency Decomposition

Based on Phase 1-3 testing, here is how the 15s SLA is distributed:

| Component | Avg Latency | % of Success Total | Bottleneck Level |
|-----------|-------------|--------------------|------------------|
| **Embedding** | 50-80 ms | ~1% | Low |
| **Qdrant Search** | 30-50 ms | < 1% | Low |
| **SQLite Fetch** | 10-20 ms | < 1% | Low |
| **Classifier (Groq)** | 2,500-4,000 ms | ~45% | **CRITICAL** (Rate Limited) |
| **Generation (Groq)** | 3,000-5,000 ms | ~50% | **HIGH** (Rate Limited) |

## Identified Bottlenecks

### 1. External API Quota (The "Wall")
- **Impact**: 80% failure rate at 5 concurrent users.
- **Root Cause**: Reliance on free/low-tier API keys for both Groq and Gemini.
- **Observation**: Cascading failures occur when both primary and fallback providers hit limits simultaneously.

### 2. Classifier Latency
- **Impact**: Adds ~3-4s to every request regardless of complexity.
- **Observation**: Even on successful requests, the classifier is the single largest contributor to latency after generation.

### 3. Qdrant Resource Constraints
- **Impact**: Minimal (Current load).
- **Observation**: Qdrant RAM remained stable at ~1.8GB. However, the 4GB limit is a potential future bottleneck as the corpus or user count grows beyond 100 concurrent users.

## Optimization Roadmap (Phase 12-13)

### Priority 1: Hybrid Classifier Strategy
- Implement a **Local Classifier** (e.g., FastText or a small fine-tuned BERT) for 90% of common queries.
- Reserve LLM classification only for high-ambiguity or complex legal queries.

### Priority 2: Semantic Caching
- Use Qdrant to find "similar enough" past queries.
- If a high-confidence match is found, serve the cached IRAC answer directly.
- **Impact**: Reduces API cost and latency to < 200ms for cached hits.

### Priority 3: Streaming UI
- Ensure the Frontend properly handles streaming tokens.
- **Impact**: Reduces "perceived latency" even if the total generation time remains at 5-10s.

## Conclusion
The **RAG Core is Production-Ready**. The **Orchestration Layer is NOT**. 
The current "All-LLM" architecture is too fragile for public deployment without significant API quota increases or architectural shifts toward local processing.
