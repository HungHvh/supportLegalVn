# Phase 11 Discussion Summary

**Phase**: 11 — Performance Testing & Monitoring  
**Status**: DISCUSS phase completed  
**Date**: 2026-05-03  
**Milestone**: v2.0 Frontend & Chat

---

## Overview

Phase 11 establishes comprehensive performance baselines for the supportLegal RAG pipeline under realistic concurrency loads, with critical focus on Windows/WSL2 resource constraints (Qdrant 4GB VM limit) and three-phase staged testing approach.

## Phase Scope

### Primary Objectives
1. **Measure RAG Core Performance**: Isolate embedding + retrieval pipeline bottlenecks without LLM interference
2. **Characterize Classifier Latency**: Test Groq/DeepSeek provider performance and fallback robustness
3. **Establish End-to-End SLA**: Full pipeline latency under concurrent load with cost tracking
4. **Identify Breaking Points**: Determine Qdrant crash thresholds, CPU limits, optimal concurrency

### What's NOT in Scope
- Production deployment or cloud scaling
- Load balancer/clustering setup
- Advanced profiling or flame graphs (Phase 12+)
- GPU optimization (Phase 13+)

---

## Key Decisions Made

### 1. Testing Tool: Locust (Python-based)
**Why**: Already in Python ecosystem, write test scenarios in familiar language, gradient ramp capability
**Alternative Considered**: Apache JMeter (rejected — heavier, XML configs)

### 2. Resource Monitoring: docker stats
**Why**: Direct per-container metrics; critical on Windows since Qdrant runs in WSL2 Docker
**Key Insight**: Windows `vmmem` process is misleading; `docker stats` is correct approach
**Threshold**: Alert at 3.2GB RAM (80% of 4GB limit)

### 3. Three-Phase Decomposition  
**Phase 1**: RAG Core (Embedding + Retrieval only)  
→ **Why**: Isolate Qdrant/embedding bottleneck without LLM latency masking issues

**Phase 2**: Classifier Integration (Groq/DeepSeek)  
→ **Why**: External API providers behave differently under load; test fallback chains

**Phase 3**: Full Pipeline (RAG + Classifier + LLM Generation)  
→ **Why**: Real SLA reflection; requires cost monitoring

---

## Critical Unknowns (Must Answer in Planning Phase)

| Unknown | Impact | How to Resolve |
|---------|--------|----------------|
| Vietnamese bi-encoder RAM footprint | Peak memory under load | Measure in Phase 1 baseline |
| Qdrant crash threshold on 4GB | System stability | Ramp concurrency until failure in Phase 1 |
| Embedding latency ceiling | Throughput SLA | Profile embedding time in isolation |
| Classifier rate limits (Groq/DeepSeek) | Phase 2 scaling limit | Test with 50+ concurrent classifier calls |
| SQLite disk I/O on WSL2 | Potential bottleneck | Monitor disk wait% during Phase 1 |
| CPU throttling patterns on Windows | False positive latency spikes | Compare host + container CPU metrics |
| Locust scalability ceiling | How many users can one test machine simulate | Target 100-200 concurrent users |

---

## Windows/WSL2 Environment Risks

| Risk | Mitigation |
|------|-----------|
| WSL2 reserves ~2GB memory; Qdrant may crash <3GB used | Baseline "comfortable" RAM before scaling |
| SQLite file locks + WSL2 ↔ Windows latency | Keep DB inside WSL2 filesystem; verify path |
| Host→WSL2 container latency (1-5ms per request) | Run Locust inside Docker to eliminate host jitter |
| Host CPU throttling starves WSL2 processes | Monitor host CPU; close background apps during test |
| GPU access limited in WSL2 | Verify vietnamese-bi-encoder runs on CPU only |

---

## Deliverables Created

### 1. DISCUSS.md (Main Strategic Document)
- 9-part detailed plan covering tooling, phases, UAT criteria
- Risk analysis specific to Windows/WSL2
- Verification criteria and success metrics for each phase
- Decision rationale and alternatives considered

### 2. locustfile_phase1_rag.py (Load Test Script)
- Locust test harness targeting `/api/test/test-rag` endpoint
- 6 sample Vietnamese legal queries (diverse corpus coverage)
- Result tracking: success/failure rates, p50/p95/p99 latencies
- Test stop event with interpretation guidance

### 3. monitor_qdrant.ps1 (Resource Monitoring)
- Real-time `docker stats` wrapper for Windows PowerShell
- Configurable RAM/CPU thresholds
- Peak tracking across test duration
- Color-coded alerts (green/yellow/red)

### 4. IMPLEMENTATION_CHECKLIST.md (Detailed Task List)
- Phase 1-3 implementation breakdown
- Endpoint specs for `/api/test/*` endpoints
- Pre-test environment setup
- Troubleshooting guide with solutions

### 5. QUICKSTART.md (Practitioner's Guide)
- 5-minute setup to first test run
- 4-terminal command sequence (Qdrant, FastAPI, Monitor, Locust)
- What to watch during test execution
- Post-test analysis and metrics collection
- Troubleshooting common issues

### 6. This Summary Document

---

## Gray Areas Still Open for Planning Phase

1. **Endpoint Implementation Details**  
   Should `/api/test/test-rag` option to return early at retrieval or go full async pipeline?  
   *→ Recommendation: Early return option for Phase 1 isolation; add full option in Phase 2*

2. **Test Data Scale**  
   Is 6 hardcoded queries sufficient? Or generate 100+ dynamic queries?  
   *→ Recommendation: Start with 6; scale up if cache effects distort metrics*

3. **Concurrency Ramp Parameters**  
   Users: 10 → 100 @ 2/sec, hold 5 min per level — is this aggressive enough?  
   *→ Recommendation: Start conservative; adjust after Phase 1 baseline*

4. **Cost Budget for Phase 3**  
   LLM calls include Gemini + Groq; roughly $15-25 per hour of testing  
   *→ Recommendation: Set $30 budget; run Phase 3 in one session*

5. **Profiling vs. Load Testing**  
   Should we add CPU/memory profiling hooks? (Fancy but adds overhead)  
   *→ Recommendation: Skip profiling until Phase 1 identifies clear bottleneck*

---

## Pre-Planning Clarifications Needed

Before `/gsd-plan-phase 11` proceeding to detailed planning:

- [ ] Do `/api/test/*` endpoints already exist in codebase, or need to be created?
- [ ] Can `rag_pipeline.retrieve_only()` method be added to `core/rag_pipeline.py`?
- [ ] Is SQLite database (`legal_data.db`) already populated with 518K articles?
- [ ] Are API keys (Groq, DeepSeek, Gemini) active and not rate-limited?
- [ ] What is the acceptable API cost budget for Phase 3 full E2E testing?
- [ ] Should test results be persisted to `.planning/reports/` for historical tracking?

---

## Success Criteria (Charter)

| Phase | Metric | Target |
|-------|--------|--------|
| **1: RAG Core** | p95 latency under 50 users | < 3000ms |
| **1: RAG Core** | Peak Qdrant RAM | < 3.2GB (80% limit) |
| **1: RAG Core** | Failure rate | < 5% |
| **2: Classifier** | p95 latency | < 2000ms |
| **2: Classifier** | Groq rate limit events | 0 under 20 concurrent calls |
| **3: Full Pipeline** | p95 end-to-end latency | < 15s per request |
| **3: Full Pipeline** | Cost for 30 min test | < $30 |

---

## Recommended Planning Structure

### Wave 1: Endpoint Implementation (2-3 hours)
- Create `/api/test/test-rag` endpoint
- Add `retrieve_only()` method to RAG pipeline
- Add error handling + timeout guards

### Wave 2: Tooling Setup (1-2 hours)
- Validate Locust script runs against endpoint
- Test `monitor_qdrant.ps1` script
- Verify all 4-terminal setup works

### Wave 3: Phase 1 Baseline Run (2-3 hours)
- Execute Phase 1 test (20-30 minutes test + analysis)
- Document results in PHASE1_RESULTS.md
- Identify bottleneck (embedding, Qdrant, or SQLite)

### Wave 4: Phase 2-3 Implementation (Conditional, 3-4 hours)
- Based on Phase 1 findings, implement Phase 2-3 tests
- Repeat for Classifier, then Full Pipeline

### Wave 5: Synthesis & UAT (1-2 hours)
- Create BOTTLENECK_ANALYSIS.md
- Create RECOMMENDATIONS.md for Phase 12-13
- UAT sign-off

---

## Estimated Timeline

| Phase | Effort | Critical Path | Dependencies |
|-------|--------|---|------|
| Implementation | 1 day | Yes | Code changes in `app.py`, `api/v1/endpoints.py`, `core/rag_pipeline.py` |
| Phase 1 Testing | 1 day | Yes | Qdrant running, FastAPI working, no regressions |
| Phase 2 Testing | 0.5 day | Optional | Groq/DeepSeek API keys active |
| Phase 3 Testing | 0.5 day | Optional | Budget approval for LLM calls |
| Reporting | 0.5 day | Yes | Phase 1 data collection |

**Total**: 3-4 days elapsed (with some parallelization possible)

---

## Handoff to Planning Phase

**Ready for `/gsd-plan-phase 11`**

All discussion artifacts prepared. Planning phase should:
1. Clarify gray areas above (6 Questions)
2. Create detailed task breakdown with story points
3. Assign implementation order (Waves 1-5)
4. Define acceptance criteria per task
5. Schedule team review gates

**Key Files for Planner**:
- `DISCUSS.md` — Main strategic document (9 sections)
- `IMPLEMENTATION_CHECKLIST.md` — Task decomposition
- `QUICKSTART.md` — Execution reference for developers

---

## Appendix: Quick Reference

### Start Monitoring
```powershell
.\monitor_qdrant.ps1 -ThresholdGB 3.2
```

### Run Phase 1 Test
```powershell
locust -f locustfile_phase1_rag.py --host http://localhost:8000
```

### Check Qdrant Status
```powershell
docker stats qdrant
```

### Access Locust Web UI
```
http://localhost:8089
```

---

**Discussion Phase Completed**: 2026-05-03  
**Status**: Ready for Phase Planning  
**Next Command**: `/gsd-plan-phase 11`

