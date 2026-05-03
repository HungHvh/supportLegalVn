# Phase 11 Implementation Checklist

## Pre-Test Setup

### Environment Preparation
- [ ] Ensure Qdrant is running: `docker-compose up -d`
- [ ] Verify Qdrant container has 4GB limit: `docker inspect qdrant | grep -i memory`
- [ ] Verify FastAPI app is ready to be started
- [ ] Install Locust: `pip install locust` (in Python venv)
- [ ] Review docker-compose.yml for resource limits

### Data Preparation
- [ ] Verify SQLite database exists and is populated (legal_data.db)
- [ ] Verify Qdrant has embedded vectors (518K documents expected)
- [ ] Verify Vietnamese bi-encoder model is cached/available

## Phase 1: RAG Core Baseline

### Implementation Tasks
- [ ] Create `/api/test/test-rag` endpoint in `api/v1/endpoints.py`
  - [ ] Accepts POST with `{"query": "string"}`
  - [ ] Calls `rag_pipeline.retrieve_only(query)` (may need to add this method)
  - [ ] Fetches full_content from SQLite for top 5 results
  - [ ] Returns elapsed_ms timing
  - [ ] Error handling for timeouts, Qdrant unavailable, etc.

### Test Execution
- [ ] Terminal 1: Start Qdrant if not running: `docker-compose up -d`
- [ ] Terminal 2: Start FastAPI: `python -m uvicorn app:app --reload --port 8000`
- [ ] Terminal 3: Start monitoring: `.\monitor_qdrant.ps1 -ThresholdGB 3.2`
- [ ] Terminal 4: Start Locust: `locust -f locustfile_phase1_rag.py --host http://localhost:8000`
- [ ] Browser: Open http://localhost:8089
  - [ ] Set spawn rate: 2 users/sec
  - [ ] Start with 10 users
  - [ ] Gradually increase to 100 users or until breakpoint
  - [ ] Run for 15-30 minutes

### Observation & Data Collection
- [ ] Monitor Qdrant RAM in Terminal 3 (watch for 3.2GB threshold)
- [ ] Watch p95 latency trend in Locust web UI
- [ ] Note CPU utilization in Terminal 3
- [ ] Record failure rate changes
- [ ] Identify user count where performance degrades

### Analysis & Documentation
- [ ] Export final Qdrant peak RAM, CPU%, user count from test
- [ ] Document p50, p95, p99 latencies from Locust report
- [ ] Create Phase1_Results.md with findings:
  - [ ] At what user count does p95 exceed 3000ms?
  - [ ] Peak RAM usage vs. 4GB limit?
  - [ ] CPU usage pattern (linear vs. cliff)?
  - [ ] Any error categories?
- [ ] Root cause analysis:
  - [ ] Is bottleneck in embedding generation?
  - [ ] Is it Qdrant retrieval?
  - [ ] Is it SQLite full_content fetch?

## Phase 2: Classifier Testing (Planned)

### Endpoint Implementation
- [ ] Create `/api/test/test-classifier` endpoint
  - [ ] Accepts POST with `{"query": "string"}`
  - [ ] Tests Groq classifier (primary)
  - [ ] Falls back to DeepSeek if Groq fails
  - [ ] Returns: classifier_provider, latency, result
- [ ] Create `/api/test/test-rag-with-classifier` endpoint
  - [ ] Combines retrieval + classifier

### Test Execution
- [ ] Similar ramp profile as Phase 1 (monitor for Groq API rate limits)
- [ ] Track API calls to external providers
- [ ] Document fallback activation

## Phase 3: Full Pipeline E2E (Planned)

### Implementation
- [ ] Use existing `/api/v1/chat` or `/api/v1/ask` endpoint
- [ ] Add cost tracking (API calls to Gemini/Groq)
- [ ] Set test duration limit (5 min max) to control costs

### Execution
- [ ] Run with lower concurrency (10 concurrent users)
- [ ] Track cumulative API costs every 60 seconds
- [ ] Document end-to-end latency breakdown

## Reporting & Handoff

- [ ] Create RESULTS.md summarizing all three phases
- [ ] Create BOTTLENECK_ANALYSIS.md identifying optimization priorities
- [ ] Create ROADMAP_NEXT.md suggesting Phase 12-13 focus areas
- [ ] Present findings for Phase 11 UAT sign-off

## Known Risks & Mitigations

- [ ] **WSL2 Memory Pressure**: Pre-test with small load; don't run other apps
- [ ] **SQLite Lock**: Ensure DB file on WSL2 filesystem, not Windows mount
- [ ] **API Costs**: Phase 3 testing can incur $5-20; budget accordingly
- [ ] **Test Contamination**: Use distinct queries to avoid caching
- [ ] **Qdrant Crash**: If it occurs, check OOM events in `docker logs qdrant`

## Troubleshooting

### FastAPI won't start
- Check port 8000 is free: `netstat -ano | findstr :8000`
- Check venv is activated: `pip list | findstr fastapi`

### Locust can't connect to localhost:8000
- Verify FastAPI is running: `curl http://localhost:8000/docs`
- If in WSL2, try http://host.docker.internal:8000 from Locust inside Docker
- Otherwise, run Locust directly on host with FastAPI

### Qdrant memory spike then crash
- Check current usage: `docker stats`
- Check logs: `docker logs qdrant | tail -50`
- Reduce user ramp rate (slower == lower peak memory)
- Increase index segment refresh interval

### High latency but Qdrant RAM/CPU low
- Embedding model may be single-threaded; check python CPU usage
- Check SQLite disk I/O: `perfmon` on Windows
- May need to increase Qdrant search_timeout parameter

---

*Last Updated: 2026-05-03*
*Status: Ready for Phase 1 implementation*

