# Phase 11: Quick Start Guide - Run First Performance Test

## TL;DR - Start Testing in 5 Minutes

### Terminal 1: Ensure Qdrant is Running
```powershell
cd C:\Users\hvcng\PycharmProjects\supportLegalVn
docker-compose up -d
# Verify: docker ps (should show qdrant container)
```

### Terminal 2: Start FastAPI Server
```powershell
cd C:\Users\hvcng\PycharmProjects\supportLegalVn
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn locust  # if not already installed
python -m uvicorn app:app --reload --port 8000
# You should see: Uvicorn running on http://0.0.0.0:8000
```

### Terminal 3: Monitor Qdrant Resources
```powershell
cd C:\Users\hvcng\PycharmProjects\supportLegalVn\.planning\phases\11-performance-testing-monitoring
.\monitor_qdrant.ps1
# Watch for RAM usage and CPU% in real-time
```

### Terminal 4: Start Load Test with Locust
```powershell
cd C:\Users\hvcng\PycharmProjects\supportLegalVn
locust -f .planning\phases\11-performance-testing-monitoring\locustfile_phase1_rag.py --host http://localhost:8000
# You should see: Starting web interface at http://0.0.0.0:8089
```

### Browser: Open Locust Web UI
```
http://localhost:8089
```

In the web UI:
1. **Number of users to simulate**: `10`
2. **Spawn rate (users started/second)**: `2`
3. Click green **[Start swarming]** button

### What to Watch

**Locust Web UI** (http://localhost:8089):
- Response Time Graph (should climb slowly, then plateau)
- Users graph (should climb from 10 to current count)
- Requests/sec (measure of throughput)
- Failure rate (should stay near 0%)

**Terminal 3 - Monitor Output** (watch for warnings):
```
14:23:05 | RAM: 2.1 GB OK | CPU: 45.2% | Peak RAM: 2.3 GB
14:23:10 | RAM: 2.3 GB OK | CPU: 52.1% | Peak RAM: 2.3 GB
14:23:15 | RAM: 2.2 GB ⚠ WARNING | CPU: 48.5% | Peak RAM: 2.3 GB  
```

- Green = Normal
- Yellow = Watch (RAM > 2.56GB, which is 80% of 3.2GB threshold)
- Red = Alert (RAM > 3.2GB, time to stop test!)

## When to Stop the Test

Stop when ANY of these happen:

✓ Completed 20 minutes without issues → Stop manually, review results
🔴 RAM hits 3.2GB (threshold) → Click **[Stop]** immediately
🔴 Failure rate jumps > 5% → Stop immediately
🔴 Latency p95 > 10 seconds → Likely Qdrant under severe pressure, stop

## After Test Completes

### 1. Export Locust Results
In Locust web UI, scroll down:
- Click **"Download Data"** → saves CSV with detailed stats
- Screenshot the "Statistics" table

### 2. Check Final Terminal 3 Output
Note the "Peak RAM" value printed, e.g., `Peak RAM: 2.8 GB`

### 3. Check FastAPI Logs (Terminal 2)
Look for any errors like:
- `Connection refused` (Qdrant crashed)
- `Timeout` (slow retrieval)
- `500 Internal Server Error` (code bug)

### 4. Record Key Metrics
Create `.planning/phases/11-performance-testing-monitoring/PHASE1_RESULTS.md`:

```markdown
# Phase 1 Test Results

**Date**: YYYY-MM-DD  
**Duration**: 20 minutes  
**Peak Users**: 50  

## Latency (milliseconds)
- P50: 245ms
- P95: 1,230ms
- P99: 2,100ms

## Resource Usage
- Peak RAM: 2.8 GB (70% of 4GB limit)
- Peak CPU: 72%

## Success Rate
- Successful requests: 12,450
- Failed requests: 23
- Success rate: 99.8%

## Analysis
- Latency scales linearly with user count
- No significant memory leak (RAM stabilized)
- Bottleneck appears to be embedding generation (CPU peaked)

## Recommendations
- **Short term**: Current performance is acceptable for production MVP
- **Medium term**: Consider GPU acceleration for embedding model
- **Long term**: Implement embedding caching layer
```

## Next Phase

When Phase 1 looks good, proceed to Phase 2:
- Test Classifier separately (Groq/DeepSeek)
- Measure classifier latency in isolation
- Create similar load test for `/api/test/test-classifier` endpoint

## Troubleshooting

### Problem: "Connection refused" from Locust
**Solution**: 
1. Verify FastAPI running: `curl http://localhost:8000/docs`
2. Verify endpoint exists: `curl -X POST http://localhost:8000/api/test/test-rag -H "Content-Type: application/json" -d '{"query":"test"}'`
3. If 404, need to add endpoint to `api/v1/endpoints.py`

### Problem: Locust shows 0 requests
**Solution**:
1. Check Locust web UI shows correct host: `http://localhost:8000`
2. Click green Start button (not already running)
3. Check Terminal 2 for errors

### Problem: Qdrant uses 0 bytes in monitor
**Solution**:
1. Verify Qdrant running: `docker ps | findstr qdrant`
2. Verify it has data: `docker exec qdrant qdrant-cli --uri http://localhost:6334 collections`
3. If empty, run indexer first: `python indexer.py`

### Problem: Test stalls at 10 users
**Solution**:
1. Could be hitting API rate limit (Groq, DeepSeek, Gemini)
2. Could be embedding model saturated (single-threaded?)
3. Reduce spawn rate to 1 user/sec and continue
4. Monitor CPU — if maxed out, embedding is bottleneck

## Questions?

See full documentation in:
- `DISCUSS.md` - Detailed strategic planning
- `IMPLEMENTATION_CHECKLIST.md` - Complete task list
- `.planning/ROADMAP.md` - Overall project roadmap

---

**Ready to start?** → Go to Terminal 1 above and run `docker-compose up -d` 🚀

