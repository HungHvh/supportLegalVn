# Phase 2: Classifier Performance Results

**Date**: 2026-05-03  
**Duration**: 2 minutes (Headless, aborted)  
**Peak Users**: 20  
**Provider**: Groq (Primary) / Gemini (Fallback)

## Latency Statistics (milliseconds)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **P50** | 17,000 ms | < 1000 ms | ✗ FAIL |
| **Mean** | 12,922 ms | - | - |
| **P95** | > 20,000 ms | < 2000 ms | ✗ FAIL |
| **Success Rate** | 50.0% | > 95% | ✗ FAIL |

## Resource Usage (Qdrant)
*Not measured as this was an LLM-bound test.*

## Analysis
- **Bottleneck**: The primary bottleneck is the external LLM provider (Groq) rate limits (HTTP 429).
- **Latency**: High latencies are due to retries and timeout failures. Even successful requests are taking > 3s on average.
- **Failover**: Fallback to Gemini was triggered but did not resolve the performance issue under this concurrency level.
- **Production Risk**: The current classifier implementation cannot handle 20 concurrent users with the existing free/low-tier API keys.

## Recommendations
1. **Rate Limiting**: Implement a local rate limiter to queue classifier requests.
2. **Provider Upgrade**: Move to a production-tier Groq or Gemini account with higher QPM (Queries Per Minute).
3. **Local Classifier**: Consider a small local model (e.g., Llama-3-8B on Ollama) for classification if latency/cost is a priority.
4. **Caching**: Implement semantic caching for common queries to bypass the classifier.

## UAT Sign-Off: REJECTED ✗
The Classifier does not meet the performance target for production load. Optimization is required before scaling.
