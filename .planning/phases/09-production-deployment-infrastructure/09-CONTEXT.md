# Context: Phase 9 — Production Deployment & Infrastructure

**Status:** Decisions Locked  
**Date:** 2026-05-05  
**Owner:** Team  
**Dependency:** Phase 7 (UI complete), Phase 17 (API Gateway), Phase 18 (Performance optimized)

---

## 1. Phase Boundary

**In scope:**
- Deploy frontend to Vercel (with environment-driven API base URL).
- Deploy backend stack (FastAPI + Qdrant + SQLite) to EC2 via Docker Compose.
- Configure Nginx reverse proxy on EC2 for TLS termination, routing, SSE support.
- Implement strict CORS allowlist for production domains.
- Standardize Qdrant connectivity contract.
- Set up data persistence (Docker volumes + daily backups).
- Configure secrets injection and key rotation.
- Implement observability baseline (structured logs, health checks, basic monitoring).

**Out of scope:**
- Kubernetes orchestration (deferred to v3.0+).
- Advanced backup/disaster recovery (simple daily snapshots only).
- Multi-region high availability (single EC2 instance acceptable for Phase 9).
- Advanced metrics/APM (defer to Phase 19+).
- Custom CDN for static assets (Vercel default acceptable).

**Dependencies:**
- Phase 7: UI complete and tested locally.
- Phase 17: API Gateway layer (rate limiting, request signing) implemented.
- Phase 18: Performance optimizations applied.
- Phase 16: SSE `/api/v1/stream` endpoint stable.

---

## 2. Locked Decisions

### D1 — Deployment Topology  
**Decision:** Vercel (frontend) + EC2 Docker Compose (backend + Qdrant + SQLite).  
**Rationale:**
- Clear separation of concerns and responsibility.
- Frontend deploys quickly with Vercel's CI/CD.
- Backend data stays local and under operational control.
- Easy to monitor, restart, and debug EC2 stack autonomously.

**Artifact responsibility:**
- **Frontend:** Vercel config + env files (`NEXT_PUBLIC_API_BASE_URL` hardened per environment).
- **Backend:** `docker-compose.yml` (existing, update configs), EC2 launch scripts.

---

### D2 — Edge/Reverse Proxy  
**Decision:** Nginx on EC2 terminates TLS and proxies `/api/*` to FastAPI.  
**Rationale:**
- Production-grade reverse proxy (rate limit, gzip, security headers, SSE support).
- Single point for TLS certificate management.
- Easy to add middleware (WAF, auth, request signing).

**Artifact responsibility:**
- **Nginx config:** `/etc/nginx/sites-available/api.domain.com` or similar.
- **TLS:** Let's Encrypt cert + auto-renewal via Certbot.
- **Buffering:** `/api/v1/stream` must have `proxy_buffering off`.

---

### D3 — API Base URL Strategy  
**Decision:** Use `NEXT_PUBLIC_API_BASE_URL` environment variable; remove all hardcoded localhost references.  
**Rationale:**
- Mandatory for Vercel frontend to work at runtime.
- Allows different base URLs per environment (dev, staging, prod).
- Clean separation between build-time and runtime config.

**Environment examples:**
```
# Production (Vercel)
NEXT_PUBLIC_API_BASE_URL=https://api.domain.com

# Staging (local or staging Vercel)
NEXT_PUBLIC_API_BASE_URL=https://api-staging.domain.com

# Local development
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**Files to audit + remove hardcode:**
- `frontend/src/app/page.tsx`
- `frontend/src/hooks/useSearchHighlight.ts`
- Any other hook or component that calls `/ask`, `/stream`, `/search_articles`, etc.

---

### D4 — CORS Policy  
**Decision:** Strict allowlist by production domain; no wildcard in production.  
**Rationale:**
- Prevents unauthorized cross-origin requests from other domains.
- Production stability and security.

**Config schema (FastAPI `app.py`):**
```python
if ENVIRONMENT == "production":
    ALLOWED_ORIGINS = [
        "https://app.domain.com",
        "https://www.domain.com",  # if needed
    ]
else:
    # Dev/staging allows localhost and test origins
    ALLOWED_ORIGINS = ["*"]  # or explicit list per stage
```

**Responsibility:**
- Backend: tighten `ALLOWED_ORIGINS` in `app.py` before deployment.
- Verify: CORS response headers match only whitelisted domains.

---

### D5 — Qdrant Connectivity Contract  
**Decision:** Canonical env vars are `QDRANT_HOST`, `QDRANT_PORT=6334`, `prefer_grpc=True` (as implemented in `retrievers/qdrant_retriever.py`).  
**Rationale:**
- Explicit, consistent, easy to validate on startup.
- gRPC offers better performance than HTTP for local connections.
- Reduces ambiguity vs. `QDRANT_URL` format.

**Fallback (optional):**
- If `QDRANT_URL` is provided in future, treat as fallback only, not canonical.

**Validation at startup:**
- Backend must validate both env vars are set and Qdrant is reachable.
- Fail fast if connectivity test fails (before serving traffic).

---

### D6 — Retriever Production Mode  
**Decision:** `legal_articles` is the primary and canonical collection for production.  
**Rationale:**
- Reduces ambiguity and confusion during debugging.
- Supports modern article-level retrieval (from Phase 10+ re-indexing).
- All production queries use `aretrieve_articles()`.
- Legacy fallback `legal_chunks` kept only for backwards compatibility or emergency rollback, not active use.

**Code lockdown:**
- `retrievers/qdrant_retriever.py::aretrieve_articles()` is the entrypoint for production.
- `self.collection_name` must default to `"legal_articles"` and not be overridden in production config.
- Logging must identify which collection is used per query.

---

### D7 — Data Persistence & Backup  
**Decision:** Persistent Docker volumes + daily snapshot backup for SQLite and Qdrant data.  
**Rationale:**
- Docker volumes ensure data survives container restarts.
- Daily snapshots protect against corruption or accidental deletion.
- Simple and maintainable (no complex backup orchestration in Phase 9).

**Implementation:**
- `docker-compose.yml`: define volumes for SQLite, Qdrant storage, and embedding cache.
- Backup cron job (runs daily on EC2 host):
  - Snapshot SQLite: `cp legal_poc.db legal_poc.db.backup-$(date +%Y%m%d)`
  - Snapshot Qdrant: export snapshots via Qdrant API or copy data directory.
  - Retain last 7 days of snapshots.
- Disaster recovery: documented procedure to restore from snapshot.

**RPO/RTO target:** ~1 day data loss acceptable; recovery within 1 hour.

---

### D8 — Streaming/SSE Through Proxy  
**Decision:** Keep SSE enabled in production (`/api/v1/stream`); Nginx must disable buffering for this endpoint.  
**Rationale:**
- SSE provides real-time streaming for chat responses — critical UX feature.
- Buffering would delay or lose stream chunks.
- Disabling buffering only for `/api/v1/stream` keeps other endpoints fast.

**Nginx config snippet:**
```nginx
location /api/v1/stream {
    proxy_buffering off;
    proxy_pass http://backend:8000;
    proxy_set_header Connection "upgrade";
    proxy_set_header Upgrade $http_upgrade;
}
```

**Testing:**
- Verify stream output is not delayed when proxied through Nginx.
- Test with long-running requests (30+ seconds).

---

### D9 — Secrets & Key Management  
**Decision:** Inject secrets via environment variables or secret store; rotate all exposed keys before go-live.  
**Rationale:**
- No secrets in git or docker images.
- Environment-driven config supports rotation without redeployment.
- Pre-deployment audit ensures no leaked keys in production.

**Required actions before go-live:**
1. Audit git history for exposed keys (GitHub/Groq/Gemini/Qwen/DeepSeek API keys).
2. Rotate and regenerate all keys used in `.env` file.
3. Remove `.env` from git (ensure `.gitignore` includes it).
4. Set up Vercel secrets for frontend env vars.
5. Set up EC2 secrets manager or `.env` file from secure source (not committed).

**Env var schema (backend `app.py`):**
```python
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", SAFE_EMBEDDING_MODEL_NAME)
---
# Must validate all required keys are set on startup
```

---

### D10 — Observability & Operations  
**Decision:** Structured logs + `/health` checks + basic resource monitoring + alerts on errors.  
**Rationale:**
- Minimal operational overhead for Phase 9.
- Enough signal to diagnose issues and alert on failures.
- Foundation for Phase 19+ advanced APM.

**Minimum required:**

| Component | Metric/Check | Implementation |
|-----------|--------------|-----------------|
| **FastAPI** | Structured logs (JSON) | Use Python logging with JSON formatter. |
| **FastAPI** | 5xx error rate | Log all 500 errors with request ID. |
| **FastAPI** | `/health` endpoint | Return `{"status": "ok"}` if all dependencies reachable. |
| **Qdrant** | Health check in `/health` | Verify Qdrant connection, return error if down. |
| **SQLite** | Health check in `/health` | Verify DB file accessible, return error if locked/missing. |
| **EC2 host** | CPU, RAM, disk usage | CloudWatch agent or simple `top`/`df` monitoring. |
| **EC2 host** | Container restart count | Monitor `docker ps --filter status=exited`. |
| **Nginx** | Reverse proxy errors | Log 4xx, 5xx responses to file, tail for alerts. |
| **Alerts** | Error spike detection | If 5xx errors > 10% over 5 min window, alert ops. |

**Log shipping (optional for Phase 9):**
- Logs written to `/var/log/` on EC2.
- No external log aggregation required yet (but leave hook for Phase 19).

---

## 3. Implementation Artifacts

### Frontend (Vercel)

| File | Change | Details |
|------|--------|---------|
| `frontend/src/app/page.tsx` | Remove hardcode `http://localhost:8000` | Use `process.env.NEXT_PUBLIC_API_BASE_URL`. |
| `frontend/src/hooks/useSearchHighlight.ts` | Remove hardcode localhost | Use env-driven base URL. |
| `frontend/next.config.ts` | Ensure env vars exported | `NEXT_PUBLIC_API_BASE_URL` must be available at runtime. |
| `.env.local` (local dev only) | Add `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` | Not committed; per-developer override. |
| (Vercel dashboard) | Add production env vars | `NEXT_PUBLIC_API_BASE_URL=https://api.domain.com` (per branch). |

### Backend (EC2 Docker Compose)

| File | Change | Details |
|------|--------|---------|
| `app.py` | Tighten `ALLOWED_ORIGINS` | Lock to production domains; validate startup. |
| `docker-compose.yml` | Add volume mounts | Ensure SQLite, Qdrant data persisted to named volumes. |
| `docker-compose.yml` | Add health checks | Implement `healthcheck:` for FastAPI and Qdrant services. |
| Infrastructure script | Nginx config + TLS setup | Deploy config, enable Certbot auto-renewal. |
| Infrastructure script | Backup cron job | Daily snapshot script for SQLite, Qdrant. |
| `.env` (EC2 via secret store) | Add secrets | `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `ALLOWED_ORIGINS` (list). |

### Observability

| Component | Artifact | Details |
|-----------|----------|---------|
| **Logging** | JSON formatter in `app.py` | Structured logs to stdout/file. |
| **Health endpoint** | `GET /health` in API | Return status of all dependencies. |
| **Metrics** | CloudWatch agent config (optional) | EC2 CPU, RAM, disk to CloudWatch dashboard. |

---

## 4. Downstream Dependencies & Sequences

### A. Frontend changes must complete first:
1. Remove localhost hardcodes.
2. Add `NEXT_PUBLIC_API_BASE_URL` env var support.
3. Test locally against `http://localhost:8000` backend.
4. Commit and merge to main.

### B. Backend infrastructure setup (parallel):
1. Provision EC2 instance (Ubuntu 22.04 LTS recommended).
2. Install Docker, Docker Compose, Nginx, Certbot.
3. Clone repo to EC2.
4. Create `.env` file with production secrets (from secure source).
5. Test `docker-compose up` locally on EC2.

### C. Verification (sequence):
1. Deploy backend to EC2; verify `/health` endpoint returns 200.
2. Configure Nginx with TLS; test reverse proxy routing to FastAPI.
3. Test SSE through Nginx: `curl -N https://api.domain.com/api/v1/stream?query=test`
4. Deploy frontend to Vercel with `NEXT_PUBLIC_API_BASE_URL=https://api.domain.com`.
5. Test frontend → Nginx → FastAPI end-to-end.
6. Verify CORS: check response headers only allow production domains.

### D. Monitoring & operational checks:
1. Verify `/health` returns 200 and all dependencies listed.
2. Verify structured logs in `/var/log/`.
3. Test alert on fake 5xx errors.
4. Verify daily backup cron job runs and saves snapshots.

---

## 5. Gray Areas Resolved & Locked

| Area | Gray | Decision | Rationale |
|------|------|----------|-----------|
| Frontend deployment target | Vercel or self-hosted? | **Vercel** | Fast deploy, managed SSL, env-driven config. |
| Backend hosting | ECS/EKS or Docker Compose? | **EC2 + Docker Compose** | Simpler operational model; no K8s overhead. |
| Reverse proxy | Nginx, HAProxy, or cloud LB? | **Nginx** | Lean, battle-tested, easy config. |
| Domain structure | Single domain or multi-subdomain? | **Single domain + `/api/*` path** | Nginx routes all via one TLS cert. |
| Qdrant protocol | HTTP or gRPC? | **gRPC (6334)** | Better perf, already in code. |
| Collection strategy | `legal_articles` or configurable? | **`legal_articles` hardcoded** | Clearer intent, easier debug. |
| Backup frequency | Daily, hourly, continuous? | **Daily** | Sufficient, simple cron job. |
| SSE support | Keep or remove? | **Keep** | Critical UX; Nginx config designed for it. |
| Secrets rotation | Manual or automated? | **Manual rotation pre-go-live** | Automated rotation deferred to Phase 19. |
| Monitoring depth | Logs only or full APM? | **Logs + `/health` + basic metrics** | Sufficient for Phase 9 stability; APM Phase 19+. |

---

## 6. Success Criteria

- [x] All 10 deployment decisions locked and documented.
- [ ] Frontend API base URL is environment-driven (no localhost hardcodes).
- [ ] Backend Docker Compose includes persistent volumes and health checks.
- [ ] Nginx reverse proxy configured with TLS and SSE support.
- [ ] CORS allowlist tightened to production domains.
- [ ] Qdrant connectivity validated on startup.
- [ ] Daily backup cron job operational.
- [ ] Environment variables injected securely (no secrets in git).
- [ ] `/health` endpoint returns 200 with all dependencies.
- [ ] Frontend → Nginx → Backend chain works end-to-end.
- [ ] Structured logs written to disk.
- [ ] Monitoring alerts configured (e.g., 5xx spike).

---

## 7. Planning Handoff

**To Planner:** Use this CONTEXT.md to create detailed `09-PLAN.md`.

**Expected PLAN.md structure:**
1. **Step 1:** Audit and update frontend for env-driven base URL.
2. **Step 2:** Tighten backend CORS policy and add startup validation.
3. **Step 3:** Update `docker-compose.yml` with volumes and health checks.
4. **Step 4:** Create Nginx config + TLS setup script.
5. **Step 5:** Create backup/restore scripts.
6. **Step 6:** Add structured logging and `/health` endpoint.
7. **Step 7:** Deploy stack to EC2 and verify e2e.
8. **Step 8:** Deploy frontend to Vercel and verify connectivity.
9. **Step 9:** Run smoke tests and operational acceptance tests (OAT).
10. **Step 10:** Document runbook and on-call procedures.

---

## 8. References & Artifacts

- **Phase 7 artifacts:** `07-CONTEXT.md`, `07-PLAN.md`, `07-SUMMARY.md`
- **Phase 17 artifacts:** API Gateway rate limiting, request signing.
- **Phase 18 artifacts:** Performance optimizations (Qdrant tuning, retriever caching).
- **Code references:**
  - `app.py` (FastAPI entry)
  - `docker-compose.yml`
  - `retrievers/qdrant_retriever.py`
  - `frontend/src/app/page.tsx`
  - `frontend/src/hooks/useSearchHighlight.ts`

---

**Context locked. Ready for planning.**

