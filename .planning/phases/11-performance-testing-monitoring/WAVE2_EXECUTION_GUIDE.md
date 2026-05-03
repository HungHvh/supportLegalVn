# Phase 11: Wave 2 Execution Guide

**Wave 2: Phase 1 RAG Core Baseline Testing**  
**Duration**: 20-30 minutes of load testing (+ 1 hour analysis)  
**Status**: Ready for execution  
**Date Reference**: 2026-05-03

---

## ⚠️ IMPORTANT: 4-Terminal Setup Required

Wave 2 MUST be executed in 4 separate terminals running simultaneously. Do NOT try to run sequentially.

---

## Pre-Execution Checklist

Before starting any terminals, verify:

- [ ] Wave 1 infrastructure complete (test endpoint, retrieve_only() method)
- [ ] api/v1/endpoints.py modified (contains TestRAGRequest and test-rag endpoint)
- [ ] core/rag_pipeline.py modified (contains retrieve_only() method)
- [ ] Qdrant running: `docker ps | grep qdrant` shows container
- [ ] Locust installed: `pip freeze | grep locust`
- [ ] Monitor script exists: `ls .planning/phases/11-performance-testing-monitoring/monitor_qdrant.ps1`
- [ ] FastAPI can start: `python -m uvicorn app:app --port 8000` (Ctrl+C to stop)

---

## 4-Terminal Architecture

### Terminal A: Qdrant (Already Running - Verify Only)

```powershell
# Verify Qdrant is running with 4GB limit
docker ps | Select-String "qdrant"

# Expected output:
# fdec9fed2600   qdrant/qdrant:latest  ... Up 6 hours ... 0.0.0.0:6333-6334->6333-6334/tcp

# Verify 4GB memory limit
docker inspect qdrant | Select-String "Memory"
```

**Status**: Qdrant should already be running from Wave 1 setup  
**Action**: Just verify it's healthy. If not running: `docker-compose up -d`

---

### Terminal B: FastAPI Server

**Start this FIRST after verifying Qdrant**

```powershell
# Navigate to project root
cd C:\Users\hvcng\PycharmProjects\supportLegalVn

# Activate venv
.\.venv\Scripts\Activate.ps1

# Start FastAPI
python -m uvicorn app:app --reload --port 8000

# Expected output:
# Uvicorn running on http://0.0.0.0:8000
# Application startup complete
```

**Keep this terminal open for entire test duration**  
**DO NOT close or it will terminate the test**

---

### Terminal C: Resource Monitor

**Start this AFTER FastAPI is ready**

```powershell
# Navigate to phase directory
cd C:\Users\hvcng\PycharmProjects\supportLegalVn\.planning\phases\11-performance-testing-monitoring

# Start monitor with 3.2GB threshold (80% of 4GB limit)
.\monitor_qdrant.ps1 -ThresholdGB 3.2 -IntervalSeconds 5

# Expected output (sample):
# 14:23:05 | RAM: 2.1 GB OK | CPU: 45.2% | Peak RAM: 2.1 GB
# 14:23:10 | RAM: 2.2 GB OK | CPU: 48.1% | Peak RAM: 2.2 GB
# 14:23:15 | RAM: 2.3 GB ⚠ WARNING | CPU: 52.5% | Peak RAM: 2.3 GB
# ...

# Watch for:
# - Green = Normal
# - Yellow = Approaching threshold (2.56-3.2GB)
# - Red = ALERT (> 3.2GB) — STOP TEST IMMEDIATELY if this happens
```

**Keep this terminal open for entire test duration**  
**This is your real-time resource monitor**

---

### Terminal D: Locust Load Test (THE MAIN TEST)

**Start this LAST after FastAPI is ready**

```powershell
# Navigate to project root
cd C:\Users\hvcng\PycharmProjects\supportLegalVn

# Option 1: HEADLESS MODE (Automated, runs 20 minutes)
locust -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py `
  --host http://localhost:8000 `
  --users 100 `
  --spawn-rate 2 `
  --run-time 20m `
  --headless `
  --csv=.planning/reports/phase1_baseline

# Expected output:
# Spawning 0 (of 100) concurrent Locust users at rate 2 per second
# Spawning 2 concurrent Locust users at rate 2 per second
# ...
# (test runs for 20 minutes with periodic updates)

# When complete:
# ===================================================================
# Type     Name                  #reqs  #fails  Avg    Min   Max   Med  95%
# POST     /api/v1/test-rag      XXXX   YY      ZZZms  ...
# ===================================================================
# *** TaskSet statistics
# ...
```

**Option 2: WEB UI MODE (Manual control)**

Use this if you want to adjust parameters during test:

```powershell
locust -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py `
  --host http://localhost:8000

# Then:
# 1. Open http://localhost:8089 in browser
# 2. Set "Number of users to simulate": 10
# 3. Set "Spawn rate (users started/second)": 2
# 4. Click green [Start swarming] button
# 5. Watch graphs update in real-time
# 6. Increase users gradually: Set to 20, 50, 100 (adjust spawn rate as needed)
# 7. Run for 20-30 minutes
# 8. Click red [Stop] button when done
# 9. Click [Download Data] to export CSV
```

**Recommendation**: Use headless mode for first run (automated)

---

## Test Execution Timeline

### T+0 min: All terminals started

```
Terminal A: Qdrant verified running ✅
Terminal B: FastAPI listening on :8000 ✅
Terminal C: Resource monitor showing RAM/CPU ✅
Terminal D: Locust starting to ramp users ✅
```

### T+1 min: Initial ramp (10 users)

- Locust: Starting to send requests
- Monitor: RAM should be stable, around 2.0-2.3GB
- FastAPI: Logs showing incoming requests
- Expected: p95 latency ~200-400ms

### T+5 min: Mid ramp (20-30 users)

- Locust: Ramping continues (2 users/sec)
- Monitor: RAM gradually increasing
- FastAPI: High request throughput
- Expected: p95 latency ~300-600ms

### T+10 min: Heavy load (50+ users)

- Locust: Approaching peak concurrency
- Monitor: RAM peak usually occurs here
- FastAPI: Under sustained load
- Expected: p95 latency ~800-1200ms

### T+15-20 min: Peak load (100 users @ 2/sec ramp)

- Locust: Full concurrency reached
- Monitor: Maximum RAM utilization
- FastAPI: Sustained under peak load
- Expected: p95 latency ~1200-2000ms

### T+20 min: Test complete

- Locust: Final statistics printed
- Monitor: Peak RAM value confirmed
- FastAPI: Still responsive
- Output: CSV exported, results ready for analysis

---

## What to Watch During Test

### Terminal C - Resource Monitor (Most Important!)

Watch for RED alerts (RAM > 3.2GB):
- If RED appears → **IMMEDIATELY STOP test** (Ctrl+C in Terminal D)
- If YELLOW → Note the time; continue but prepare to stop

Track the peak RAM value appearing on each line.

### Terminal B - FastAPI Logs

Watch for errors:
- `500 Internal Server Error` → Endpoint issue
- `ConnectionError` → Qdrant connection lost
- `Timeout` → Requests taking too long (expected at peak)

### Terminal D - Locust Output

Watch for statistics updates showing:
- Requests per second
- Success rate
- Failure types
- Response time percentiles

---

## Expected Values (Success Criteria from PLAN.md)

If test results match these, Wave 2 PASSES:

| Metric | Expected | Target | Status |
|--------|----------|--------|--------|
| **Test Duration** | 20-30 min | Uninterrupted | ✓ |
| **Peak Users Reached** | 100 | ≥ 50 | ✓ |
| **Total Requests** | 1000+ | ≥ 500 | ✓ |
| **P95 Latency** | 1000-2000ms | < 3000ms | ✓ PASS |
| **Peak RAM** | 2.5-3.0GB | < 3.2GB | ✓ PASS |
| **Success Rate** | 98-100% | > 95% | ✓ PASS |
| **Failure Rate** | 0-2% | < 5% | ✓ PASS |

---

## Quick Validation Test (Before Full 20-min Test)

Run this in Terminal D first to verify setup works:

```powershell
locust -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py `
  --host http://localhost:8000 `
  --users 5 `
  --spawn-rate 1 `
  --run-time 1m `
  --headless

# Should complete with 40-60 requests, ~0% failures
```

If this passes → Ready for full 20-minute test

---

## Data Collection During Test

### From Locust (Terminal D)

After test completes, Locust prints:
- Response time percentiles (50th, 95th, 99th)
- Total requests and failures
- Requests per second

Copy this output to a text file for later analysis.

### From Monitor (Terminal C)

Peak RAM value appears in each line. When test ends, note the final "Peak RAM" value shown.

### From FastAPI (Terminal B)

Logs show timing information:
- `EMBEDDING_LATENCY ...ms` (if using retrieve_only)
- `QDRANT_QUERY_LATENCY ...ms`
- Total elapsed time for endpoint

---

## Post-Test Analysis (Task 2.2)

After test completes, create `.planning/phases/11-performance-testing-monitoring/PHASE1_RESULTS.md`:

```markdown
# Phase 1: RAG Core Baseline Results

**Date**: [Date of test]
**Duration**: [How long test ran]
**Peak Users**: [Max concurrent users reached]
**Peak RAM**: [From monitor, e.g., 2.8 GB]

## Latency Statistics (milliseconds)
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| P50    | XXX   | -      | ✓      |
| P95    | XXX   | < 3000 | ✓ PASS |
| P99    | XXX   | -      | ✓      |

## Success Rate
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Success | XX.X% | > 95%  | ✓ PASS |
| Failures | YY  | < 5%   | ✓ PASS |

## Bottleneck Analysis
Primary finding: [Embedding / Qdrant / SQLite] is likely bottleneck

## Recommendations
1. ...
2. ...
```

---

## Troubleshooting Wave 2

### Problem: FastAPI won't start (Terminal B)

**Solution**:
- Check port 8000 is free: `netstat -ano | findstr :8000`
- Kill existing process: `taskkill /PID <PID> /F`
- Ensure .venv activated
- Try different port: `--port 8001`

### Problem: Locust shows 0 requests (Terminal D)

**Solution**:
- Verify FastAPI running: `Test-NetConnection localhost -Port 8000`
- Verify endpoint: `Invoke-WebRequest http://localhost:8000/api/v1/test-rag -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"query":"test"}'`
- Check Locust host: Ensure `--host http://localhost:8000` is correct
- If using web UI: Make sure you clicked [Start swarming] button

### Problem: Qdrant RAM hits 3.2GB (RED alert in Terminal C)

**Solution** (URGENT):
- Stop test immediately: Press Ctrl+C in Terminal D
- Note the peak users where it happened
- Reduce test parameters for next attempt:
  - Max users: 50 instead of 100
  - Spawn rate: 1 instead of 2
- Restart everything and retry

### Problem: FastAPI returns 500 errors

**Solution**:
- Check FastAPI logs (Terminal B) for detailed error
- Verify Qdrant running: `docker ps | Select-String qdrant`
- Check database accessible: `ls legal_poc.db`
- Restart FastAPI

---

## After Wave 2 Complete

When all tasks done:

1. ✅ Collect final metrics from Locust output
2. ✅ Note peak RAM from monitor
3. ✅ Check FastAPI logs for any errors
4. ✅ Create PHASE1_RESULTS.md with data
5. ✅ Determine if criteria passed: p95 < 3000ms, RAM < 3.2GB, success > 95%
6. ✅ Identify bottleneck (retrieve_only timing breakdown)
7. ✅ Decision: Proceed to Phase 2 or optimize Phase 1

---

## Quick Start (Copy-Paste)

**Terminal A** (verify):
```powershell
docker ps | Select-String "qdrant"
```

**Terminal B** (FastAPI):
```powershell
cd C:\Users\hvcng\PycharmProjects\supportLegalVn
.\.venv\Scripts\Activate.ps1
python -m uvicorn app:app --reload --port 8000
```

**Terminal C** (Monitor):
```powershell
cd C:\Users\hvcng\PycharmProjects\supportLegalVn\.planning\phases\11-performance-testing-monitoring
.\monitor_qdrant.ps1 -ThresholdGB 3.2
```

**Terminal D** (Test):
```powershell
cd C:\Users\hvcng\PycharmProjects\supportLegalVn
locust -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py --host http://localhost:8000 --users 100 --spawn-rate 2 --run-time 20m --headless --csv=.planning/reports/phase1_baseline
```

---

**Status**: ✅ Wave 2 Setup Complete  
**Next**: Execute with 4 terminals simultaneously  
**Duration**: 20-30 minutes for full test  
**Output**: PHASE1_RESULTS.md with baseline metrics


