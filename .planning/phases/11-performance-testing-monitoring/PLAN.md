# Phase 11 Plan: Performance Testing & Monitoring

**Phase**: 11 — Performance Testing & Monitoring  
**Milestone**: v2.0 Frontend & Chat  
**Status**: PLAN (ready for execution)  
**Date Created**: 2026-05-03  
**Last Updated**: 2026-05-03

---

## Executive Summary

Execute a three-wave performance testing campaign against the supportLegal RAG pipeline to establish baselines under concurrent load, identify bottlenecks (Qdrant memory, classifier latency, LLM generation cost), and validate SLA targets before production deployment. This plan decomposes discussion artifacts into 12 executable tasks with acceptance criteria, resource monitoring, and UAT gates.

**Goal**: Answer "Can the system handle production load safely within current resource constraints (4GB Qdrant, Windows/WSL2)?"

**Success Criteria**:
- ✅ Phase 1 RAG Core: p95 < 3000ms, RAM < 3.2GB, success rate > 95%
- ✅ Phase 2 Classifier: p95 < 2000ms, fallback working
- ✅ Phase 3 Full Pipeline: p95 < 15s @ 10 users, API cost < $30
- ✅ Team decision: "Approve production deployment" or "Allocate Phase 12 for optimization"

---

## Phase Scope & Objectives

### What's Included
1. **RAG Core Baseline** (Embedding + Retrieval isolation)
2. **Classifier Performance** (Groq/DeepSeek provider testing)
3. **Full Pipeline E2E** (Real SLA measurement)
4. **Bottleneck Analysis** (Optimization recommendations)

### What's NOT Included
- Production deployment or cloud scaling
- Advanced profiling (flame graphs, kernel tracing)
- GPU optimization (deferred to Phase 12+)
- Load balancing or clustering

---

## WAVE 1: Test Infrastructure Setup (2-3 hours)

### Task 1.1: Create `/api/test/test-rag` Endpoint (Isolated RAG Testing)

**Objective**: Implement a hidden test endpoint that measures RAG performance without LLM or classifier interference; focuses on embedding + retrieval isolation.

**Owner**: [TBD - Backend Engineer]  
**Effort**: 1.5 hours  
**Dependencies**: None (setup task)

**Acceptance Criteria**:
- [ ] Endpoint `/api/test/test-rag` exists and responds to POST requests
- [ ] Request accepts JSON: `{"query": "string"}`
- [ ] Response returns JSON with fields: `{"query": str, "top_results_count": int, "full_contents_count": int, "elapsed_ms": float, "status": str, "retrieval_ms": float, "sqlite_fetch_ms": float}`
- [ ] Endpoint calls `rag_pipeline.retrieve_only(query)` (method to be added in Task 1.2)
- [ ] Fetches full_content from SQLite for top 5 results
- [ ] Handles timeouts gracefully (returns 408 after 30 sec)
- [ ] Handles Qdrant unavailability (returns 503 with detail)
- [ ] Logs timing: "ENDPOINT_START", "RETRIEVE_DURATION", "SQLITE_FETCH_DURATION", "ENDPOINT_COMPLETE"

**Implementation Code**:
```python
# File: api/v1/endpoints.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import time
import logging
import asyncio

logger = logging.getLogger(__name__)

class TestRAGRequest(BaseModel):
    query: str

router = APIRouter(prefix="/api/test", tags=["testing"])

@router.post("/test-rag")
async def test_rag_endpoint(request: TestRAGRequest):
    """
    Isolated RAG performance test — bypass Classifier and LLM.
    Purpose: Measure embedding + Qdrant retrieval + SQLite content fetch latency
    """
    if not request.query or len(request.query.strip()) == 0:
        raise HTTPException(status_code=400, detail="query cannot be empty")
    
    start_time = time.time()
    query = request.query.strip()
    
    try:
        logger.info(f"ENDPOINT_START query={query[:50]}")
        
        # Retrieve from Qdrant
        retrieval_start = time.time()
        retrieval_results = await rag_pipeline.retrieve_only(query)
        retrieval_duration = (time.time() - retrieval_start) * 1000
        logger.info(f"RETRIEVE_DURATION {retrieval_duration:.2f}ms")
        
        # Fetch full_content from SQLite
        sqlite_start = time.time()
        full_contents = []
        for result in retrieval_results[:5]:
            content = retrieve_full_article_content(result.id)
            full_contents.append({
                "id": result.id,
                "score": result.score,
                "content_len": len(content) if content else 0
            })
        sqlite_duration = (time.time() - sqlite_start) * 1000
        logger.info(f"SQLITE_FETCH_DURATION {sqlite_duration:.2f}ms")
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"ENDPOINT_COMPLETE elapsed={elapsed:.2f}ms")
        
        return {
            "query": query,
            "top_results_count": len(retrieval_results),
            "full_contents_count": len(full_contents),
            "retrieval_ms": retrieval_duration,
            "sqlite_fetch_ms": sqlite_duration,
            "elapsed_ms": elapsed,
            "status": "success"
        }
    
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request timeout")
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"test_rag_endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**Testing Verification**:
```bash
curl -X POST http://localhost:8000/api/test/test-rag \
  -H "Content-Type: application/json" \
  -d '{"query":"Tội trộm cắp tài sản"}' | jq

# Expected: {"query": "...", "elapsed_ms": 245.3, "status": "success"}
```

---

### Task 1.2: Add `retrieve_only()` Method to RAG Pipeline

**Objective**: Extend `core/rag_pipeline.py` with a method that performs embedding + Qdrant retrieval without classifier or LLM generation.

**Owner**: [TBD - Backend Engineer]  
**Effort**: 1 hour  
**Dependencies**: Task 1.1

**Acceptance Criteria**:
- [ ] Method `async retrieve_only(query: str, top_k: int = 15) -> List[Dict]` exists
- [ ] Calls embedding model to vectorize query
- [ ] Performs Qdrant search with exact parameters used in production
- [ ] Returns list with fields: `id`, `score`, `metadata`
- [ ] Handles embedding timeout (> 10 sec) with exception
- [ ] Handles Qdrant connection failure with exception
- [ ] Logs "EMBEDDING_LATENCY: {ms}ms", "QDRANT_QUERY_LATENCY: {ms}ms"

**Code Sample**:
```python
# File: core/rag_pipeline.py

async def retrieve_only(self, query: str, top_k: int = 15):
    """Retrieve from Qdrant without classification or generation."""
    import time
    
    # Embedding
    embed_start = time.time()
    query_vector = await self.embeddings.embed_query(query)  # timeout: 10s
    embed_duration = (time.time() - embed_start) * 1000
    logger.info(f"EMBEDDING_LATENCY {embed_duration:.2f}ms")
    
    # Qdrant search
    qdrant_start = time.time()
    results = await self.qdrant.search(
        collection_name="articles",
        query_vector=query_vector,
        limit=top_k,
        score_threshold=0.0
    )
    qdrant_duration = (time.time() - qdrant_start) * 1000
    logger.info(f"QDRANT_QUERY_LATENCY {qdrant_duration:.2f}ms")
    
    return results
```

**Testing Verification**:
```python
# tests/test_rag_pipeline.py

import asyncio
from core.rag_pipeline import RAGPipeline

async def test_retrieve_only():
    rag = RAGPipeline()
    results = await rag.retrieve_only("Luật đất đai 2024", top_k=10)
    
    assert len(results) > 0
    assert len(results) <= 10
    assert all("id" in r for r in results)
    assert all("score" in r for r in results)
    print("✓ retrieve_only() works")

asyncio.run(test_retrieve_only())
```

---

### Task 1.3: Validate Locust Load Test Script

**Objective**: Ensure `locustfile_phase1_rag.py` is ready and can connect to test endpoint.

**Owner**: [TBD - QA Engineer]  
**Effort**: 0.5 hours  
**Dependencies**: Task 1.1

**Acceptance Criteria**:
- [ ] Script imports without errors: `python -c "from locustfile_phase1_rag import *"`
- [ ] Locust web UI appears at http://localhost:8089 when run
- [ ] Can set user count (10, 50, 100)
- [ ] Can set spawn rate (1, 2, 5 users/sec)
- [ ] "Start swarming" sends requests to `/api/test/test-rag`
- [ ] Web UI shows response statistics: Avg, Min, Max, Median, 95%, 99%
- [ ] Final summary printed to console

**Validation Commands**:
```powershell
# Terminal 1: FastAPI
python -m uvicorn app:app --reload --port 8000

# Terminal 2: Locust (quick validation)
locust -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py `
  --host http://localhost:8000 `
  --users 5 `
  --spawn-rate 1 `
  --run-time 30s `
  --headless

# Output should show:
# Type     Name                  #reqs  #fails  Avg    Min    Max    Med    95%
# POST     /api/test/test-rag    150    0       245    87     1230   200    950
```

---

### Task 1.4: Validate docker stats Monitoring Script

**Objective**: Ensure `monitor_qdrant.ps1` correctly parses and alerts on Qdrant resource usage.

**Owner**: [TBD - DevOps/QA Engineer]  
**Effort**: 0.5 hours  
**Dependencies**: None

**Acceptance Criteria**:
- [ ] Script starts without errors: `.\monitor_qdrant.ps1`
- [ ] Displays every 5 sec: `HH:MM:SS | RAM: X.XX GB [status] | CPU: Y.Y% | Peak RAM: Z.ZZ GB`
- [ ] Color-coding works: Green (< 2.56GB), Yellow (2.56-3.2GB), Red (> 3.2GB)
- [ ] Peak RAM tracking persists (increases or stays same)
- [ ] Accepts parameters: `-ThresholdGB 3.2 -CPUThreshold 80`
- [ ] Terminates cleanly on Ctrl+C

**Validation**:
```powershell
.\monitor_qdrant.ps1 -ThresholdGB 3.2
# Output: 14:23:05 | RAM: 2.1 GB OK | CPU: 45.2% | Peak RAM: 2.1 GB
```

---

### Task 1.5: Create Baseline Environment Documentation

**Objective**: Document the test environment configuration.

**Owner**: [TBD - QA Lead]  
**Effort**: 0.5 hours  
**Dependencies**: Tasks 1.1-1.4

**Acceptance Criteria**:
- [ ] Document created: `.planning/phases/11-performance-testing-monitoring/ENVIRONMENT.md`
- [ ] Contains: Host OS, Python version, FastAPI version, Locust version, Docker version
- [ ] Contains: Qdrant config (4GB verified), SQLite location, vector count
- [ ] Contains: API keys status (Groq, DeepSeek, Gemini — no secrets, just ✓ flags)
- [ ] Contains: Pre-test checklist (Qdrant running, FastAPI ready)
- [ ] Contains: 4-terminal setup instructions

**Checklist Template (include in ENVIRONMENT.md)**:
```markdown
# Pre-Test Verification Checklist

- [ ] `docker-compose up -d` == Qdrant running
- [ ] `docker ps | grep qdrant` == Shows 4GB limit
- [ ] `python -m uvicorn app:app --reload` == FastAPI starts
- [ ] `curl http://localhost:8000/docs` == Swagger UI accessible
- [ ] `curl -X POST http://localhost:8000/api/test/test-rag -H "Content-Type: application/json" -d '{"query":"test"}'` == Endpoint responds
- [ ] `.\monitor_qdrant.ps1` == Shows RAM/CPU metrics
- [ ] `locust -f locustfile_phase1_rag.py` == Web UI at :8089
```

---

## WAVE 2: Phase 1 RAG Core Baseline Testing (3-4 hours)

### Task 2.1: Execute Phase 1 Load Test

**Objective**: Run controlled concurrency test to establish RAG core performance and identify Qdrant breaking point.

**Owner**: [TBD - QA Engineer / Performance Lead]  
**Effort**: 2.5 hours (1h setup + 30m test + 1h analysis)  
**Dependencies**: Wave 1 (all tasks)

**Acceptance Criteria**:
- [ ] Test runs ≥ 20 minutes without Qdrant crash
- [ ] Ramps from 10 → 100 users @ 2 users/sec (or until failure)
- [ ] ≥ 500 successful requests collected
- [ ] p50, p95, p99 latencies computed
- [ ] Peak Qdrant RAM recorded (target: < 3.2GB)
- [ ] Failure rate < 5% throughout
- [ ] Screenshot of Locust web UI statistics table

**Execution Script**:
```powershell
# Terminal A: Qdrant
docker-compose up -d

# Terminal B: FastAPI
.\.venv\Scripts\Activate.ps1
python -m uvicorn app:app --reload --port 8000

# Terminal C: Monitor
cd .planning/phases/11-performance-testing-monitoring
.\monitor_qdrant.ps1

# Terminal D: Locust (headless for scripted run)
locust `
  -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py `
  --host http://localhost:8000 `
  --users 100 `
  --spawn-rate 2 `
  --run-time 20m `
  --headless `
  --csv=.planning/reports/phase1_results

# OR Browser-based (manual):
# 1. Open http://localhost:8089
# 2. Set users: 10, spawn rate: 2
# 3. Click [Start swarming]
# 4. Wait 20-30 minutes
# 5. Watch for failure rate spike (STOP if > 5%)
# 6. Click [Stop], then [Download Data]
```

**Data Collection**:
- Peak RAM: ___ GB (from Terminal C)
- Peak users: ___ (from Terminal D)
- p95 latency: ___ ms (from Locust report)
- Screenshots: [saved to desktop]

---

### Task 2.2: Analyze Phase 1 Results & Create Report

**Objective**: Post-test analysis to understand bottleneck(s).

**Owner**: [TBD - Performance Engineer]  
**Effort**: 1.5 hours  
**Dependencies**: Task 2.1

**Acceptance Criteria**:
- [ ] Report created: `.planning/phases/11-performance-testing-monitoring/PHASE1_RESULTS.md`
- [ ] Contains: execution metadata (date, duration, peak users, peak RAM)
- [ ] Contains: latency statistics (p50, p95, p99, min, max)
- [ ] Contains: success rate %
- [ ] Compares against UAT criteria (✓ PASS or ✗ FAIL)
- [ ] Identifies bottleneck: "Likely [Embedding / Qdrant Query / SQLite Fetch]"
- [ ] Contains 3-5 recommendations

**Report Template**:
```markdown
# Phase 1: RAG Core Baseline Results

**Date**: 2026-05-10 | **Duration**: 25 minutes | **Peak Users**: 72

## Latency Statistics (milliseconds)
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| P95    | 1,232 | < 3000 | ✓ PASS |
| Success Rate | 99.8% | > 95% | ✓ PASS |

## Resource Usage
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Peak RAM | 2.8 GB | < 3.2 GB | ✓ PASS |

## Bottleneck Analysis
Primary finding: Qdrant retrieval ~60% of latency
Recommendation: Current perf acceptable for MVP

## UAT Sign-Off: APPROVED ✓
```

---

## WAVE 3: Phase 2 Classifier Testing (2-3 hours)

### Task 3.1: Create `/api/test/test-classifier` Endpoint

**Objective**: Implement test endpoint for Classifier latency measurement.

**Owner**: [TBD - Backend Engineer]  
**Effort**: 1.5 hours  
**Dependencies**: Task 1.1

**Acceptance Criteria**:
- [ ] Endpoint `/api/test/test-classifier` exists
- [ ] Accepts: `{"query": "string"}`
- [ ] Returns: `{"classifier_provider": str, "latency_ms": float, "category": str, "status": str}`
- [ ] Calls Groq primary; fallback to DeepSeek on timeout/rate-limit
- [ ] Records provider used: "groq" or "deepseek"
- [ ] Timeout after 10 sec max

---

### Task 3.2: Execute Phase 2 Load Test (Classifier)

**Objective**: Test Classifier latency under concurrent load; verify fallback.

**Owner**: [TBD - QA Engineer]  
**Effort**: 1.5 hours  
**Dependencies**: Task 3.1

**Acceptance Criteria**:
- [ ] Test runs 15 minutes with 20 concurrent classifier requests
- [ ] ≥ 300 successful calls collected
- [ ] **p95 latency < 2000ms**: ✓ / ✗ (actual: ___ ms)
- [ ] Fallback activation recorded
- [ ] **Fallback success rate > 95%**: ✓ / ✗
- [ ] Report: `.planning/phases/11-performance-testing-monitoring/PHASE2_RESULTS.md`

---

## WAVE 4: Phase 3 Full Pipeline E2E Testing (1.5 hours, if approved)

### Task 4.1: Execute Phase 3 Load Test (Full Pipeline)

**Objective**: Real end-to-end SLA measurement with cost tracking.

**Owner**: [TBD - QA Engineer]  
**Effort**: 1.5 hours  
**Dependencies**: Wave 2 (Phase 1 validated)

**Acceptance Criteria**:
- [ ] Test runs ≤ 5 minutes (cost control)
- [ ] ≤ 10 concurrent users (API rate limits)
- [ ] API cost tracked per request
- [ ] **Cumulative cost < $30**: ✓ / ✗ (actual: $___)
- [ ] **p95 end-to-end < 15,000ms**: ✓ / ✗ (actual: ___ ms)
- [ ] Report: `.planning/phases/11-performance-testing-monitoring/PHASE3_RESULTS.md`

**Note**: Only execute if:
1. Phase 1 approved ✓
2. Budget approved ✓
3. API keys active ✓

---

## WAVE 5: Analysis & Synthesis (2-3 hours)

### Task 5.1: Create Bottleneck Analysis

**Objective**: Synthesize all phase results into optimization recommendations.

**Owner**: [TBD - Performance Lead]  
**Effort**: 1.5 hours  
**Dependencies**: Tasks 2.2, 3.2, 4.1 (if executed)

**Acceptance Criteria**:
- [ ] Document: `.planning/phases/11-performance-testing-monitoring/BOTTLENECK_ANALYSIS.md`
- [ ] Identifies dominant latency component
- [ ] Quantifies: % latency per phase (retrieval %, classifier %, generation %)
- [ ] Recommends 3-5 optimizations for Phase 12-13
- [ ] Risk assessment: Can system handle 100+ QPS?

---

### Task 5.2: Create Project Handoff Summary

**Objective**: Prepare handoff for stakeholders.

**Owner**: [TBD - QA Lead]  
**Effort**: 1 hour  
**Dependencies**: Task 5.1

**Acceptance Criteria**:
- [ ] Document: `.planning/phases/11-performance-testing-monitoring/HANDOFF_SUMMARY.md`
- [ ] Summarizes outcomes: success criteria met or not
- [ ] Decision: "Approve prod deployment" or "Optimize first"
- [ ] Identifies Phase 12-13 priorities

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Qdrant crash** | Task 1.4 alerts at 80%; Wave 2 controlled ramp |
| **API rate limits** | Task 3.2 caps at 20 users; tests fallback |
| **SQLite locks** | Task 1.1 error handling; < 5% failure target |
| **WSL2 overhead** | Documented in Task 1.5; overhead included in baseline |
| **Cost overrun** | Phase 3 limited to 5 min + real-time tracking |

---

## Decision Points (Approval Gates)

**Gate 1: Pre-Wave 2** — Is Wave 1 infrastructure validated?
- Owner: [QA Lead]
- Criteria: All tasks complete + environment checklist passed

**Gate 2: Post-Wave 2** — If Phase 1 p95 > 5000ms, pause for optimization
- Owner: [Engineering Manager]
- Decision: Proceed to Phase 2-3 or optimize?

**Gate 3: Pre-Wave 4** — Is Phase 3 cost budget approved?
- Owner: [Product Manager / Finance]
- Budget: $30-50 for LLM calls

---

## UAT Verification Checklist

### Phase 1 Sign-Off
- [ ] Test ran ≥ 20 min uninterrupted
- [ ] **p95 < 3000ms**: ✓ / ✗ (actual: ___ ms)
- [ ] **Peak RAM < 3.2GB**: ✓ / ✗ (actual: ___ GB)
- [ ] **Success rate > 95%**: ✓ / ✗ (actual: ____ %)
- [ ] Approved by: [QA Lead] Date: ___

### Phase 2 Sign-Off (if executed)
- [ ] **p95 < 2000ms**: ✓ / ✗ (actual: ___ ms)
- [ ] **Fallback success > 95%**: ✓ / ✗
- [ ] Approved by: [QA Lead] Date: ___

### Phase 3 Sign-Off (if executed)
- [ ] **p95 < 15,000ms @ 10 users**: ✓ / ✗
- [ ] **Cost < $30**: ✓ / ✗
- [ ] Approved by: [QA Lead] Date: ___

### Overall Phase 11 Sign-Off
- [ ] All executed phases approved
- [ ] Bottleneck analysis provided
- [ ] Go/No-Go decision made
- [ ] **Approved by**: [Engineering Manager] **Date**: ___

---

## Team Assignments

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| 1.1 `/api/test/test-rag` | [TBD] | 1.5h | ⏱️ |
| 1.2 `retrieve_only()` | [TBD] | 1h | ⏱️ |
| 1.3 Validate Locust | [TBD] | 0.5h | ⏱️ |
| 1.4 Validate Monitor | [TBD] | 0.5h | ⏱️ |
| 1.5 Environment Docs | [TBD] | 0.5h | ⏱️ |
| 2.1 Phase 1 Test | [TBD] | 2.5h | ⏱️ |
| 2.2 Phase 1 Analysis | [TBD] | 1.5h | ⏱️ |
| 3.1 Classifier Endpoint | [TBD] | 1.5h | ⏱️ |
| 3.2 Phase 2 Test | [TBD] | 1.5h | ⏱️ |
| 4.1 Phase 3 Test | [TBD] | 1.5h | ⏱️ |
| 5.1 Bottleneck Analysis | [TBD] | 1.5h | ⏱️ |
| 5.2 Handoff Summary | [TBD] | 1h | ⏱️ |

**Total**: 15-18 hours (3-4 days with parallelization)

---

## Expected Deliverables

By end of Phase 11:
1. ✅ PLAN.md (this document)
2. ✅ ENVIRONMENT.md
3. ✅ PHASE1_RESULTS.md
4. ✅ PHASE2_RESULTS.md (if executed)
5. ✅ PHASE3_RESULTS.md (if executed)
6. ✅ BOTTLENECK_ANALYSIS.md
7. ✅ HANDOFF_SUMMARY.md
8. ✅ Locust CSV exports (.planning/reports/)

---

## Next Steps

1. ✅ **Review**: Engineering manager reviews plan
2. ✅ **Approve**: Teams assign owners and confirm effort estimates
3. ✅ **Kick-Off**: Execute Wave 1 (target: 1 day)
4. ✅ **Hit Gate 1**: Confirm environment ready
5. ✅ **Execute Wave 2**: Phase 1 baseline (target: 1-2 days)
6. ✅ **Gate 2**: Go/No-Go decision
7. ✅ **Execute Waves 3-5**: Complete remaining phases
8. ✅ **Final Sign-Off**: UAT checklist approved

---

**Plan Status**: READY FOR EXECUTION  
**Plan Author**: Performance Testing Working Group  
**Approval Date**: [To be scheduled]  
**Phase 11 Kickoff Target**: [To be scheduled after approval]

