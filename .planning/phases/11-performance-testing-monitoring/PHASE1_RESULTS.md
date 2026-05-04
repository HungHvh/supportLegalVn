# Phase 1: RAG Core Baseline Results

**Date**: 2026-05-03  
**Duration**: 3 minutes (Headless)  
**Peak Users**: 50  
**Ramp Rate**: 2 users/sec  

## Latency Statistics (milliseconds)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **P50** | 47 ms | < 1000 ms | ✓ PASS |
| **Mean** | 66 ms | - | - |
| **P95** | 160 ms | < 3000 ms | ✓ PASS |
| **P99** | 382 ms | - | - |
| **Success Rate** | 100.0% | > 95% | ✓ PASS |

## Resource Usage (Qdrant)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Peak RAM** | 1.8 GB | < 3.2 GB | ✓ PASS |
| **Peak CPU** | 47.5% | < 80% | ✓ PASS |

## Analysis
- **Performance**: The RAG core (embedding + retrieval) is extremely performant, with p95 well below the 3s target.
- **Scalability**: Latency remained stable as users ramped to 50.
- **Stability**: No failures were observed during the test duration.
- **Bottlenecks**: Neither CPU nor RAM reached critical levels. The system can likely handle significantly higher concurrency.

## UAT Sign-Off: APPROVED ✓
The RAG Core baseline exceeds performance requirements. Proceeding to Wave 3 (Classifier Testing).
