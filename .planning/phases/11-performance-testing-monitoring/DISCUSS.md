# Phase 11 Discussion: Performance Testing & Monitoring

## Executive Summary

**Goal**: Establish comprehensive performance baselines and stress testing for the supportLegal RAG pipeline under realistic concurrency loads, with special consideration for Windows/WSL2 resource constraints (4GB Qdrant VM limit).

**Scope**: Three-phase staged testing approach to isolate performance bottlenecks:
1. **Phase 1**: RAG Core (Embedding + Retrieval, bypass LLM/Classifier)
2. **Phase 2**: Classifier Integration (DeepSeek/Groq providers)
3. **Phase 3**: Full Pipeline (RAG + Classifier with LLM generation)

**Why This Matters**: Current system has not been load-tested at scale. Query performance, classifier latency, and Qdrant memory consumption under concurrency are unknown unknowns that could impact production SLAs.

**Critical Constraint**: Qdrant runs in Docker with 4GB RAM limit via docker-compose.yml — must identify exact breaking points before scaling to cloud infrastructure.

---

## Part 1: Tooling & Monitoring Strategy

### Load Testing Tool: Locust

- **Choice**: Locust (Python-based, already in ecosystem)
- **Alternative Considered**: Apache JMeter (heavier), wrk (HTTP-only, no custom logic)
- **Rationale**: Write test scenarios in pure Python, integrate with project's existing test helpers, simulate realistic Vietnamese legal queries, and ramp concurrency gradually to observe failure modes

### Resource Monitoring: docker stats

**Critical Insight**: On Windows with WSL2 backend, all container resources appear as a single `vmmem` process in Task Manager. Direct observation is misleading.

**Correct Approach**:
```powershell
# Run in PowerShell while load test is executing
docker stats

# Output shows per-container metrics:
# CONTAINER ID  CPU %  MEM USAGE / LIMIT  MEM %
# qdrant        35%    3.2GB / 4GB        80%
```

**Automated Monitoring** (proposed):
- Wrap `docker stats` output into CSV logging
- Alert when Qdrant hits 80% RAM (~3.2GB)
- Capture CPU throttling indicators

### Machine Profile (User's Environment)
- Host: Windows machine
- Qdrant: 4GB RAM limit (in docker-compose.yml)
- Embedding Model: `vietnamese-bi-encoder` (bkai-foundation-models)
- LLM Providers: Groq (primary classifier), DeepSeek (classifier backup), Gemini (fallback for RAG) — all external API calls
- SQLite: Local file-based for full_content retrieval

---

## Part 2: Phase 1 Design — RAG Core Testing

### Objective
Measure CPU and RAM pressure of the retrieval + embedding pipeline **without** LLM or classifier latency confounding factors. Identify Qdrant breaking point on 4GB constraint.

### Implementation

#### Step 2.1: Create Hidden Test Endpoint

**File**: `api/v1/endpoints.py` (or new `api/v1/tests.py`)

```python
from fastapi import APIRouter, HTTPException
from core.rag_pipeline import RAGPipeline
from db.sqlite import retrieve_full_article_content

router = APIRouter(prefix="/api/test", tags=["testing"])

rag_pipeline = RAGPipeline()  # Singleton, shared connection

@router.post("/test-rag")
async def test_rag_only(request: dict):
    """
    Isolated RAG test endpoint — skip Classifier & LLM.
    
    Request: {"query": "Tội trộm cắp tài sản"}
    Response: {"query": str, "top_results": [...], "full_contents": [...], "elapsed_ms": float}
    """
    query = request.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    
    import time
    start = time.time()
    
    try:
        # Step 1: Embedding + Qdrant retrieval (no Classifier)
        retrieval_results = await rag_pipeline.retrieve_only(query)
        
        # Step 2: Fetch full_content from SQLite for each result
        full_contents = []
        for result in retrieval_results[:5]:  # Cap at top 5
            content = retrieve_full_article_content(result.id)
            full_contents.append(content)
        
        elapsed = (time.time() - start) * 1000  # ms
        
        return {
            "query": query,
            "top_results_count": len(retrieval_results),
            "full_contents_count": len(full_contents),
            "elapsed_ms": elapsed,
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Note**: Assumes `rag_pipeline.retrieve_only()` method exists (may need to add it to `core/rag_pipeline.py`).

#### Step 2.2: Locust Test Script

**File**: `locustfile_phase1_rag.py`

```python
from locust import HttpUser, TaskSet, task, between, events
import random
import json
from datetime import datetime

# Sample Vietnamese legal queries to avoid Qdrant caching effects
LEGAL_QUERIES = [
    "Tội trộm cắp tài sản",
    "Đăng ký kết hôn cần gì",
    "Luật đất đai 2024",
    "Xử lý vi phạm giao thông",
    "Hợp đồng lao động 30 ngày",
    "Quyền thừa kế pháp định",
    "Vi phạm bản quyền sách",
]

# Global tracking
test_results = {
    "success": 0,
    "failure": 0,
    "responses_ms": [],
}

class RAGTasks(TaskSet):
    @task
    def test_rag_endpoint(self):
        query = random.choice(LEGAL_QUERIES)
        with self.client.post(
            "/api/test/test-rag",
            json={"query": query},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    test_results["success"] += 1
                    test_results["responses_ms"].append(data.get("elapsed_ms", 0))
                    response.success()
                except Exception as e:
                    test_results["failure"] += 1
                    response.failure(f"Invalid JSON: {e}")
            else:
                test_results["failure"] += 1
                response.failure(f"Status {response.status_code}")

class LegalRAGUser(HttpUser):
    tasks = [RAGTasks]
    wait_time = between(1, 3)  # 1-3 seconds between requests per simulated user

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print final statistics."""
    if test_results["responses_ms"]:
        import statistics
        avg_ms = statistics.mean(test_results["responses_ms"])
        p95_ms = sorted(test_results["responses_ms"])[int(len(test_results["responses_ms"]) * 0.95)]
        print(f"\n=== PHASE 1 RAG TEST RESULTS ===")
        print(f"Success: {test_results['success']}")
        print(f"Failure: {test_results['failure']}")
        print(f"Avg Latency: {avg_ms:.2f}ms")
        print(f"P95 Latency: {p95_ms:.2f}ms")
        print(f"================================\n")
```

**To run**:
```powershell
# Terminal 1: FastAPI server
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Terminal 2: Locust load test
locust -f locustfile_phase1_rag.py --host http://localhost:8000

# Terminal 3: Monitor Qdrant resources (PowerShell)
docker stats --no-stream=false
```

Then open http://localhost:8089 in browser, start with 10 users, ramp +2 users/sec until failure observed.

#### Step 2.3: Monitoring Protocol

| Metric | How to Measure | Alert Threshold | Action |
|--------|----------------|-----------------|--------|
| **Qdrant RAM** | `docker stats` → MEM USAGE | >3.2GB (80% of 4GB) | Reduce user load 50%, investigate memory leak |
| **Qdrant CPU** | `docker stats` → CPU % | >80% sustained | Observe if embedding generation is bottleneck |
| **RAG Endpoint p95** | Locust report | >5000ms | Indicates Qdrant saturated or retrieval slow |
| **Failure Rate** | Locust report | >5% | Network timeouts, Qdrant crashed |

---

## Part 3: Phase 2 Design — Classifier Testing

### Objective
Test Classifier (Groq/DeepSeek) latency in isolation, then measure combined Classifier + Retrieval pipeline without full LLM generation.

### Key Unknowns
- Does Groq have rate limits under concurrent load? (External API)
- DeepSeek fallback robustness if primary rate-limited?
- Classifier p95 latency baseline (for SLA planning)?

### Implementation Sketch
- Create `/api/test/test-classifier-only` endpoint
- Locust script simulates classifier calls with random query categories
- Monitor: Groq API error rates, response times, fallback activation

---

## Part 4: Phase 3 Design — Full Pipeline Testing

### Objective
End-to-end RAG + Classifier + LLM generation under concurrent load.

### Key Differences from Phase 1
- LLM calls are NOT mocked — real Gemini/Groq requests
- Measures true SLA impact of cascading provider latencies
- Risk: Could incur API costs during testing

### Proposed Safeguard
- Set Locust duration limit to 5 minutes max
- Track API costs in real-time
- Test in off-peak hours if APIs are metered

---

## Part 5: Risk Analysis — Windows/WSL2 Environment

### Risk 1: Memory Pressure from WSL2 Overhead
- **Problem**: WSL2 reserves ~2GB for system, even with 4GB limit allocated
- **Symptom**: Qdrant crashes at < 3GB usage
- **Mitigation**: Pre-test with small load; baseline "comfortable" RAM level before scaling

### Risk 2: Disk I/O Bottleneck on SQLite
- **Problem**: SQLite file locks + network latency (WSL2 ↔ Windows) if DB on Windows path
- **Symptom**: Phase 1 CPU doesn't scale proportionally to users; high disk wait%
- **Mitigation**: Ensure `legal_data.db` or `tmp_legal_poc.db` located inside WSL2 filesystem (not /mnt/c/)

### Risk 3: Network Latency Between Host & WSL2
- **Problem**: Locust on Windows host → FastAPI in WSL2 container adds 1-5ms per request
- **Symptom**: Baseline latencies artificially high; difficult to distinguish container overhead vs. query logic
- **Mitigation**: Run Locust inside WSL2 container to eliminate host↔container latency, or run within Docker service

### Risk 4: CPU Throttling on Windows
- **Problem**: Host OS task scheduler may starve WSL2 processes
- **Symptom**: CPU% reports low but Qdrant becomes unresponsive
- **Mitigation**: Monitor host CPU (not just container CPU); pause other apps during test window

### Risk 5: GPU Access Limitations
- **Problem**: If Qdrant or embedding model benefits from GPU, WSL2 GPU sharing is limited
- **Symptom**: Embedding generation slower than expected on CUDA-capable hardware
- **Mitigation**: Verify embedding model (vietnamese-bi-encoder) runs on CPU only; no GPU dependency assumed

---

## Part 6: Gray Areas & Key Decisions Needed

### 6.1 Endpoint Design Decision

**Question**: Should `/api/test-rag` return early at retrieval or go full pipeline?

| Option | Pros | Cons |
|--------|------|------|
| **A: Skip LLM** (proposed) | Isolated Qdrant perf testing; clear bottleneck attribution | Doesn't reflect real SLA |
| **B: Mock LLM** | More realistic pipeline; consistent response times | Hides true LLM latency variability |
| **C: Full LLM** (Phase 3 only) | True end-to-end SLA | API costs; hard to pinpoint bottleneck |

**Recommendation**: Proceed with Option A for Phase 1, then Option C in Phase 3 after baseline established.

### 6.2 Test Data Scale

**Question**: Is 4 sample queries sufficient, or do we need 100+ distinct queries to characterize Qdrant memory growth and cache behavior?

**Current Proposal**: Start with 7 queries (already defined in LEGAL_QUERIES list above). Scale up if memory doesn't stabilize after 1000 requests.

### 6.3 Concurrency Ramp Parameters

**Question**: How fast to ramp users? How long to hold at each level?

| Parameter | Proposed | Rationale |
|-----------|----------|-----------|
| Initial Users | 10 | Avoid immediate crash; baseline normal behavior |
| Ramp Rate | +2 users/sec | Slow enough to observe gradual degradation |
| Hold Time | 3-5 min per level | Allows Qdrant memory stabilization |
| Max Users | 100 (or failure) | Stop if >5% failure rate or RAM > 3.2GB |

### 6.4 Qdrant Memory Profiling Unknowns

**Critical Questions**:
- At what concurrency does Qdrant first spike RAM? (10 users? 50?)
- Does Qdrant have a known memory leak under sustained load?
- How quickly does it recover RAM after load drops?
- What is the vector index memory footprint? (Likely ~1.5-2.5GB for 518K vectors)

**How to Answer**: Run Phase 1 test, collect docker stats every 5 seconds, plot RAM over time.

---

## Part 7: Verification Criteria & UAT Sign-Off

### Phase 1: RAG Core Baseline

**Must Pass**:
- [ ] Endpoint `/api/test-rag` created and responds within 3000ms (p95)
- [ ] Locust test completes 30 min duration without crash
- [ ] Qdrant RAM never exceeds 3.2GB (80% threshold)
- [ ] Failure rate < 5% across all user counts
- [ ] CPU % pattern documented (should increase linearly with users until bottleneck)

**Should Have**:
- [ ] Collect 50+ distinct response times; compute p50, p95, p99
- [ ] Identify the user count at which p95 latency increases > 50%
- [ ] Root cause analysis: Is bottleneck Embedding generation, Qdrant query, or SQLite fetch?

**Nice to Have**:
- [ ] Docker stats logged to CSV for post-test analysis
- [ ] Grafana dashboard showing real-time metrics (optional advanced setup)

### Phase 2: Classifier Baseline

**Must Pass**:
- [ ] Classifier provider (Groq primary, DeepSeek backup) responds within 2000ms (p95)
- [ ] Fallback mechanism tested (force Groq failure, verify DeepSeek takes over)
- [ ] No API rate limit errors under 20 concurrent classifier calls

**Should Have**:
- [ ] Classifier latency distribution (p50, p95, p99) documented
- [ ] Groq vs. DeepSeek response time comparison

### Phase 3: Full Pipeline End-to-End

**Must Pass**:
- [ ] Full RAG+Classifier+LLM completes within 15000ms (p95) for <10 concurrent users
- [ ] Total API cost tracked and < $10 for 30-min test window
- [ ] No cascading failures (classifier timeout doesn't crash retrieval, etc.)

**Should Have**:
- [ ] Latency breakdown: retrieval %, classifier %, generation %
- [ ] Identify which provider (Groq for classifier vs. Gemini for generation) dominates wall-clock time

---

## Part 8: Tooling & Adjustments

### 8.1 Docker Stats Wrapper (Optional Advanced)

**Purpose**: Automate Qdrant memory alerting during long test runs.

**Sketch**:
```powershell
# save as monitor_qdrant.ps1
param([int]$ThresholdGB = 3)

while ($true) {
    $stats = docker stats --no-stream=true qdrant | Select-String "qdrant"
    if ($stats -match "(\d+\.?\d*)GB") {
        $usage = [float]$matches[1]
        if ($usage -gt $ThresholdGB) {
            Write-Host "ALERT: Qdrant RAM = $usage GB (threshold: $ThresholdGB GB)" -ForegroundColor Red
            # Optionally: Send Slack notification, kill Locust, etc.
        }
    }
    Start-Sleep -Seconds 5
}
```

### 8.2 Alternative Monitoring Tools

| Tool | Tradeoff | Recommendation |
|------|----------|-----------------|
| **docker stats** (proposed) | Manual, no history | Use for Phase 1 baseline |
| **Prometheus + Grafana** | Heavy setup, persistent data | Consider for Phase 3 if iterating |
| **New Relic / DataDog** | Cloud SaaS, $$$ | Not needed for local testing |

### 8.3 Test Data Generation

- **Current**: Hardcoded 7 sample queries (LEGAL_QUERIES)
- **Scale Up**: If needed, generate 100 queries from existing articles in Qdrant or SQLite

---

## Part 9: Success Criteria Summary

| Phase | Success Metric | Pass / Fail |
|-------|----------------|------------|
| **Phase 1** | p95 RAG latency < 3000ms @ 50 users; RAM < 3.2GB | TBD |
| **Phase 2** | p95 Classifier latency < 2000ms; fallback working | TBD |
| **Phase 3** | p95 end-to-end < 15s @ 10 users; API cost < $10 | TBD |

---

## Timeline & Next Steps

1. **[Before Planning]** Clarify unknowns (concurrency ramp params, test duration, cost budget)
2. **[Planning Phase]** Create detailed PLAN.md with sprint breakdown, task dependencies
3. **[Execution]** Implement endpoints, run Phase 1 test, analyze results
4. **[Iteration]** Adjust scaling parameters based on Phase 1 baseline, repeat Phase 2-3
5. **[Reporting]** Document bottleneck findings, recommend optimization priorities for Phase 12-13

---

**Status**: DISCUSS phase complete. Ready for `/gsd-plan-phase 11`.

