# Phase 11: Test Environment Configuration

**Last Updated**: 2026-05-03  
**Status**: Ready for Wave 1 execution

---

## System Profile

- **Host OS**: Windows 11 (with WSL2 backend for Docker)
- **Shell**: PowerShell v5.1+
- **Python Version**: 3.11+
- **Virtual Environment**: `.venv` (located at project root)
- **Docker Desktop Version**: 4.20+
- **Git**: Available (for version control)

---

## Qdrant Setup

### Configuration
- **Container**: `qdrant` (running via docker-compose)
- **Memory Limit**: 4GB (enforced in docker-compose.yml: `mem_limit: "4g"`)
- **Port (gRPC)**: 6333
- **Port (HTTP)**: 6334
- **Volume**: Mounted for persistence (path: `.qdrant_storage/`)

### Data State
- **Collection Name**: `articles` (production vector database)
- **Total Vectors Indexed**: 518,000+ legal articles
- **Vector Dimension**: 768 (vietnamese-bi-encoder)
- **Embedding Model**: `bkai-foundation-models/vietnamese-bi-encoder`

### Verification Command
```powershell
# Check Qdrant is running with 4GB limit
docker ps | Select-String "qdrant"

# Expected output: Should show container name "qdrant" with status "Up"

# Verify 4GB memory limit
docker inspect qdrant | Select-String -Pattern "Memory" | Select-Object -First 5
```

---

## SQLite Setup

### Database Files
- **Primary DB**: `legal_data.db` (production database)
- **POC DB**: `legal_poc.db` (development/testing)
- **Location**: Project root directory OR inside WSL2 filesystem (preferred)

### Schema
- **Table**: `legal_articles` (518,000+ rows)
  - Columns: `id`, `article_uuid`, `so_ky_hieu`, `article_title`, `full_text`
  - FTS Index: `articles_fts` on `so_ky_hieu` + `article_title` + `full_text`

### Important Windows/WSL2 Notes
- ⚠️ **Critical**: Keep SQLite database INSIDE WSL2 filesystem (not on Windows mount like `/mnt/c/`)
- Reason: Windows mounts have high I/O latency; WSL2 native access is ~100x faster
- Check current DB path: `echo $PWD` in WSL2 terminal
- If on Windows mount, copy: `cp legal_poc.db ~/legal_poc.db` (inside WSL2)

### Verification Command
```powershell
# Verify database file exists and is readable
ls legal_poc.db -ErrorAction Stop

# Expected output: File size should be > 200MB (for 518K articles)

# Verify FTS index
sqlite3 legal_poc.db ".schema legal_articles_fts" | Select-Object -First 10
```

---

## FastAPI Setup

### Configuration
- **Host**: `0.0.0.0` (accessible from localhost, Docker containers, and WSL2)
- **Port**: `8000`
- **Reload Mode**: `--reload` (enabled during development; auto-restarts on code changes)
- **Worker Threads**: 2 (Uvicorn default; configurable via workers parameter)

### Key Endpoints
- ✅ **Health Check**: `GET /health` → `{"status": "ok", ...}`
- ✅ **RAG Query**: `POST /api/v1/ask` → Full pipeline with LLM generation
- ✅ **RAG Stream**: `POST /api/v1/stream` → Streaming response
- ✅ **Test RAG Core**: `POST /api/v1/test-rag` → Isolated embedding+retrieval (Phase 11)

### Startup Verification
```powershell
# Terminal 1: Start FastAPI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m uvicorn app:app --reload --port 8000

# Output should show:
# Uvicorn running on http://0.0.0.0:8000
# Application startup complete

# Terminal 2: Verify endpoint is responding
curl http://localhost:8000/health | jq

# Expected output: {"status": "ok", "version": "1.0.0", ...}
```

---

## Locust Setup

### Tool Information
- **Version**: locust >= 2.15 (install via `pip install locust`)
- **Web UI Port**: `8089`
- **Test Script**: `.planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py`

### Load Test Profile
- **Query Pool**: 6+ Vietnamese legal queries (diverse corpus coverage)
- **Request Type**: POST to `/api/v1/test-rag` with JSON payload
- **Concurrency Model**: Multiple simulated users, each with 1-3 second think-time between requests
- **Metrics Computed**: p50, p95, p99 latencies; success/failure rates

### Startup Verification
```powershell
# Terminal 2: Start Locust (quick validation)
locust -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py `
  --host http://localhost:8000 `
  --users 5 `
  --spawn-rate 1 `
  --run-time 30s `
  --headless

# Output should show request statistics after 30 seconds

# Or use web UI:
locust -f ... --host http://localhost:8000
# Then open http://localhost:8089 in browser
```

---

## API Keys & External Providers

### Required Keys (for full pipeline testing)

❌ **Groq API Key** (optional for Phase 1, required for Phase 2)
- Env var: `GROQ_API_KEY`
- Status: [Check if active: ✓ or ✗]
- Purpose: Classifier provider (Llama-3.1 8B)
- Rate Limit: TBD (to be determined during Phase 2)

❌ **DeepSeek API Key** (optional for Phase 1, required for Phase 2)
- Env var: `DEEPSEEK_API_KEY`
- Status: [Check if active: ✓ or ✗]
- Purpose: Classifier fallback provider
- Rate Limit: TBD

❌ **Gemini API Key** (optional for Phase 1, required for Phase 3)
- Env var: `GOOGLE_API_KEY`
- Status: [Check if active: ✓ or ✗]
- Purpose: Full LLM generation provider (Phase 3 only)
- Rate Limit: TBD

### Phase-Specific API Requirements
- **Phase 1 (RAG Core)**: NO API keys needed ✓
- **Phase 2 (Classifier)**: Groq + DeepSeek keys needed
- **Phase 3 (Full E2E)**: All keys needed (Groq, DeepSeek, Gemini)

---

## Pre-Test Environment Checklist

### Docker & Qdrant Prerequisites
- [ ] Docker Desktop running (`docker ps` returns no errors)
- [ ] Qdrant container can start: `docker-compose up -d`
- [ ] Qdrant responses within 5 sec: `curl http://localhost:6334/health`
- [ ] 4GB memory limit enforced: `docker inspect qdrant | grep Memory`

### FastAPI Prerequisites
- [ ] Python 3.11+ available: `python --version`
- [ ] Virtual environment created: `ls .venv/`
- [ ] Dependencies installed: `pip freeze | grep fastapi` (should show fastapi installed)
- [ ] FastAPI starts without errors: `python -m uvicorn app:app --reload --port 8000`

### SQLite Prerequisites
- [ ] Database file exists: `ls legal_poc.db`
- [ ] FTS index present: `sqlite3 legal_poc.db ".tables" | grep articles`
- [ ] Database not locked: `fuser legal_poc.db` (on Linux/Mac; skip on Windows)
- [ ] Article count > 500K: `sqlite3 legal_poc.db "SELECT COUNT(*) FROM legal_articles;"`

### Locust Prerequisites
- [ ] Locust installed: `pip freeze | grep locust`
- [ ] Test script exists: `ls .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py`
- [ ] Can import script: `python -c "from locustfile_phase1_rag import *"`
- [ ] Can connect to endpoint: Verify via manual curl test

### Resource Monitoring Prerequisites
- [ ] PowerShell available: `powershell -Version` (should show v5.1+)
- [ ] Docker stats command works: `docker stats --no-stream=true`
- [ ] Monitor script exists: `ls .planning/phases/11-performance-testing-monitoring/monitor_qdrant.ps1`
- [ ] Can run monitor: `.\monitor_qdrant.ps1 -ThresholdGB 3.2` (Ctrl+C to stop)

---

## 4-Terminal Architecture for Wave 2 Testing

### Terminal A: Qdrant & Docker
```powershell
# Start Qdrant
docker-compose up -d
docker ps

# Status: Running in background, persistent across reboots (if compose restart policy set)
```

### Terminal B: FastAPI Server
```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app:app --reload --port 8000

# Status: Listening on http://0.0.0.0:8000
# Keep this terminal open during entire test run
```

### Terminal C: Resource Monitor
```powershell
cd .planning/phases/11-performance-testing-monitoring
.\monitor_qdrant.ps1 -ThresholdGB 3.2

# Status: Shows update every 5 seconds
# Watch for RAM exceeding 3.2GB (issue alert)
```

### Terminal D: Load Test (Locust)
```powershell
locust -f .planning/phases/11-performance-testing-monitoring/locustfile_phase1_rag.py `
  --host http://localhost:8000 `
  --users 100 `
  --spawn-rate 2 `
  --run-time 20m

# Or use web UI for manual control:
# 1. Run without --users/--spawn-rate/--headless
# 2. Open http://localhost:8089
# 3. Set users: 10, spawn rate: 2
# 4. Click [Start swarming]
```

---

## Troubleshooting Quick Reference

### Problem: "Cannot connect to Docker daemon"
**Solution**: 
- Ensure Docker Desktop is running (check taskbar)
- Restart Docker: Start Menu → Docker Desktop → Restart
- Verify: `docker ps`

### Problem: Qdrant shows as running but queries timeout
**Solution**:
- Check Qdrant health: `curl http://localhost:6334/health`
- Check memory: `docker stats qdrant` (if RAM > 3.8GB, Qdrant may be struggling)
- Restart Qdrant: `docker restart qdrant`

### Problem: FastAPI fails to start with "Address already in use"
**Solution**:
- Port 8000 already in use
- Find process: `netstat -ano | findstr :8000`
- Kill process: `taskkill /PID <PID> /F`
- Or use different port: `python -m uvicorn app:app --port 8001`

### Problem: Locust shows 0 requests
**Solution**:
- Verify endpoint exists: `curl -X POST http://localhost:8000/api/v1/test-rag -d '{"query":"test"}' -H "Content-Type: application/json"`
- Check Locust host setting: Must be `http://localhost:8000`
- Click green [Start swarming] button (if using web UI)

### Problem: Monitor script shows "Qdrant not running"
**Solution**:
- Verify container name: `docker ps | findstr qdrant`
- Verify image: Should be `qdrant/qdrant` or latest version
- Container must be named exactly `qdrant` or update script

### Problem: SQLite error "database is locked"
**Solution**:
- Close any other connections: Check if other terminals have sqlite3 open
- Increase timeout: Already handled in db.py via PRAGMA
- Move DB to WSL2 filesystem if on Windows mount: `cp legal_poc.db ~/legal_poc.db`

---

## Performance Baseline (Expected Values)

### RAG Core (Phase 1) Expectations
- **Embedding Generation**: ~50-100ms per query
- **Qdrant Search**: ~150-300ms per query
- **SQLite Fetch**: ~10-50ms per query (for top 5 articles)
- **Total p95 Latency**: < 3000ms @ 50 concurrent users (success target)
- **Peak RAM**: < 3.2GB (80% of 4GB limit)
- **Success Rate**: > 95%

### Classifier (Phase 2) Expectations (if Groq/DeepSeek keys available)
- **Groq Classification**: ~500-1000ms per query
- **DeepSeek Fallback**: ~800-1500ms per query
- **p95 Latency**: < 2000ms (success target)

### Full Pipeline (Phase 3) Expectations (if budget approved)
- **Total E2E**: Embedding + Retrieval + Classifier + LLM Generation
- **Typical**: 5-15 seconds per response @ 10 concurrent users
- **p95 Latency**: < 15,000ms (success target)
- **API Cost**: ~$0.10-0.50 per request (depends on Gemini + Groq pricing)

---

## Network Considerations for Windows/WSL2

### Host → WSL2 Container Latency
- **Typical**: 0.5-5ms per network hop
- **Impact**: Each HTTP request incurs this overhead
- **Mitigation**: Documented in test results; counted toward latency baseline

### WSL2 Filesystem Performance
- **Native WSL2 FS**: ~5000 IOPS (fast)
- **Windows Mount (/mnt/c/)**: ~100-500 IOPS (slow, avoid for SQLite)
- **Recommendation**: Keep SQLite inside WSL2 filesystem

### Memory Pressure
- **WSL2 VM Limit**: 4GB (can be increased in `.wslconfig`)
- **Qdrant 4GB Limit**: Enforced separately in docker-compose.yml
- **System Reserve**: ~1.5GB for WSL2 kernel + processes
- **Available for Qdrant**: Typically 2.5GB actual (not full 4GB due to overhead)

---

## Deliverables from Wave 1 Infrastructure Setup

After completing Wave 1, the following should be in place:

1. ✅ **Code Changes**:
   - `/api/v1/endpoints.py` → Added `@router.post("/test-rag")` endpoint
   - `core/rag_pipeline.py` → Added `async retrieve_only()` method to `LegalRAGPipeline`
   - `app.py` → RA endpoints registered under `/api/v1` prefix

2. ✅ **Validation Results**:
   - Test endpoint responds: `curl -X POST http://localhost:8000/api/v1/test-rag -d '{"query":"test"}' | jq`
   - Locust script validated: `locust -f .../locustfile_phase1_rag.py --host http://localhost:8000 --run-time 30s --headless`
   - Monitor script validated: `.\monitor_qdrant.ps1` shows RAM/CPU metrics
   - Environment documentation complete (this file)

3. ✅ **Pre-Test Status**:
   - All prerequisites met (Docker running, FastAPI ready, Locust configured)
   - Baseline environment documented
   - 4-terminal architecture ready for Wave 2 execution

---

## Next: Wave 2 Execution

**Trigger**: When Wave 1 complete and this checklist passed  
**Duration**: 1-2 days  
**Output**: Phase 1 performance baseline + analysis report

See: `.planning/phases/11-performance-testing-monitoring/QUICKSTART.md` for Wave 2 execution walkthrough

---

**Status**: ✅ Environment documentation complete  
**Ready for**: Wave 2 Phase 1 RAG Core baseline testing  
**Approval**: [Pending QA Lead verification of Wave 1 completion]

