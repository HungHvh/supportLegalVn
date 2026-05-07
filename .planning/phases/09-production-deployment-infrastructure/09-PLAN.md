# Phase 9 Plan: Production Deployment & Infrastructure

**Phase:** 9 — Production Deployment & Infrastructure  
**Milestone:** v2.0 Frontend & Chat  
**Status:** PLAN (ready for execution)  
**Date Created:** 2026-05-06  
**Source:** `.planning/phases/09-production-deployment-infrastructure/09-CONTEXT.md`

---

## Executive Summary

This phase hardens the application for production by separating frontend and backend deployment concerns, introducing a production reverse proxy, removing localhost coupling from the frontend, standardizing Qdrant connectivity, and establishing a minimum operational baseline for persistence, backups, health checks, and monitoring.

**Primary outcome:** A deployable production stack where:
- Frontend runs on **Vercel**.
- Backend runs on **EC2 + Docker Compose**.
- **Nginx** terminates TLS and proxies `/api/*` to FastAPI.
- **SSE** continues to function through the proxy.
- **SQLite + Qdrant** persist across restarts and have daily backups.
- Secrets are injected securely and rotated before go-live.

---

## Scope

### In Scope
1. Frontend runtime configuration for environment-driven API base URL.
2. Backend CORS tightening and startup validation.
3. Qdrant connectivity normalization to `QDRANT_HOST`, `QDRANT_PORT=6334`, `prefer_grpc=True`.
4. Production-ready Docker Compose persistence and health checks.
5. Nginx reverse proxy + TLS + SSE buffering configuration.
6. Backup/restore scripts for SQLite and Qdrant.
7. Structured logging, health endpoint readiness, and operational checks.
8. Vercel and EC2 deployment verification.

### Out of Scope
- Kubernetes or multi-region HA.
- Advanced APM / distributed tracing.
- Full DR automation beyond daily snapshots.
- CDN customization beyond Vercel defaults.

---

## Execution Strategy

The phase is organized into **5 waves**. Each wave has a clear gate; later waves must not proceed until earlier gates pass.

### Wave 1 — Frontend Runtime Configuration

**Goal:** Remove all hardcoded localhost API references and make the frontend deployable to Vercel.

#### Tasks
1. Update `frontend/src/app/page.tsx` to build the SSE URL from `process.env.NEXT_PUBLIC_API_BASE_URL` instead of `http://localhost:8000`.
2. Update `frontend/src/hooks/useSearchHighlight.ts` to use the same env-driven base URL for article search requests.
3. Add a small shared helper if needed (for example, a `frontend/src/lib/apiBaseUrl.ts` utility) so both call sites resolve the base URL consistently.
4. Update `frontend/README.md` with local development guidance:
   - required `.env.local` entry
   - production Vercel env value
   - example `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` for dev
5. Verify the frontend still works locally against the existing backend and that no direct localhost string remains in production code paths.

#### Files Likely Edited
- `frontend/src/app/page.tsx`
- `frontend/src/hooks/useSearchHighlight.ts`
- `frontend/README.md`
- optional helper file under `frontend/src/lib/`

#### Gate 1 — Frontend config pass
- Frontend builds successfully.
- No production request path hardcodes `http://localhost:8000`.
- Local dev remains functional with `.env.local`.
- Vercel-ready runtime config is documented.

---

### Wave 2 — Backend Contracts, CORS, and Health

**Goal:** Make backend configuration explicit and fail fast when production dependencies are misconfigured.

#### Tasks
1. Tighten CORS in `app.py` so production uses a strict allowlist, not `*`.
2. Add startup validation for production-critical environment variables:
   - `ALLOWED_ORIGINS`
   - `QDRANT_HOST`
   - `QDRANT_PORT`
   - production API keys used by the active providers
3. Ensure the `/health` endpoint reports real dependency status instead of static success.
4. If needed, align `api/models.py::HealthResponse` with the richer health payload.
5. Confirm `api/v1/endpoints.py::health` and `app.py::health_check` are not diverging; choose one canonical health surface or make them consistent.
6. Standardize the Qdrant contract in `db/qdrant.py` and `retrievers/qdrant_retriever.py` to use the locked production values and preserve `prefer_grpc=True`.
7. Ensure `legal_articles` remains the primary production retrieval path.

#### Files Likely Edited
- `app.py`
- `api/v1/endpoints.py`
- `api/models.py`
- `db/qdrant.py`
- `retrievers/qdrant_retriever.py`
- `.env.example` if it documents env contract

#### Gate 2 — Backend contract pass
- Backend starts cleanly only when required production env is present.
- `/health` reflects SQLite and Qdrant reachability.
- CORS rejects non-allowlisted origins in production mode.
- Qdrant usage is consistent across manager and retriever code.

---

### Wave 3 — Production Compose, Persistence, and Backups

**Goal:** Make the EC2 stack durable and restart-safe.

#### Tasks
1. Refine `docker-compose.yml` for production behavior:
   - named volumes for Qdrant storage and SQLite data location if needed
   - restart policies preserved
   - `healthcheck` for `api` and `qdrant`
   - safe service ordering (`depends_on` plus health awareness where feasible)
2. Confirm the Compose layout supports the locked topology: backend + Qdrant + SQLite on one EC2 host.
3. Add a backup script set, likely under `scripts/`, to snapshot:
   - SQLite database
   - Qdrant data or snapshot export
4. Add restore instructions or a restore script so recovery is repeatable.
5. Define retention rules for daily snapshots (minimum: last 7 days).

#### Files Likely Edited
- `docker-compose.yml`
- `scripts/backup_*.ps1` or `scripts/backup_*.sh`
- `scripts/restore_*.ps1` or `scripts/restore_*.sh`
- optional `docs/` runbook note

#### Gate 3 — Persistence/backups pass
- Compose starts successfully with persistent data.
- Containers restart without losing data.
- Backup jobs produce timestamped artifacts.
- Restore steps are documented and reproducible.

---

### Wave 4 — Nginx, TLS, and SSE Through Proxy

**Goal:** Put a production edge in front of the API without breaking streaming.

#### Tasks
1. Create an Nginx site config for the EC2 host.
2. Route `/api/*` to FastAPI and terminate TLS at Nginx.
3. Add SSE-safe proxy settings for `/api/v1/stream`:
   - `proxy_buffering off`
   - long read timeouts
   - headers appropriate for streaming
4. Add a bootstrap or setup script for:
   - installing Nginx
   - installing Certbot
   - enabling certificate renewal
5. Validate that non-stream endpoints and stream endpoints both work behind the proxy.

#### Files Likely Edited
- new Nginx config file under `deploy/`, `infra/`, or `scripts/`
- new EC2 setup script
- optional deployment README section

#### Gate 4 — Edge/proxy pass
- HTTPS terminates successfully on the EC2 host.
- `/api/*` reaches FastAPI through Nginx.
- `/api/v1/stream` streams without buffering delays.
- Certbot renewal path is documented.

---

### Wave 5 — Observability, Deployment Verification, and Handoff

**Goal:** Prove the stack is production-ready and document how to operate it.

#### Tasks
1. Ensure structured logging is enabled and usable from the running service.
2. Add or confirm a `/health` response that can be checked by humans and by automation.
3. Define the minimum monitoring set:
   - CPU
   - RAM
   - disk
   - container restart count
   - API 5xx spikes
   - Qdrant health
4. Run deployment verification on EC2:
   - backend health
   - Qdrant connectivity
   - SSE through Nginx
   - article search flow
   - frontend-to-backend request flow from Vercel
5. Write the operational runbook:
   - deploy steps
   - rollback steps
   - backup/restore steps
   - secret rotation steps
   - quick incident checks

#### Files Likely Edited
- `app.py` or supporting logging utilities
- `docs/` or a new `deploy/README.md`
- possibly `.planning/phases/09-production-deployment-infrastructure/09-SUMMARY.md` if the workflow expects a handoff artifact

#### Gate 5 — Production acceptance pass
- Frontend → Nginx → FastAPI works end-to-end.
- `/health` is healthy and dependency-aware.
- Logs are visible and structured.
- Backup + restore path is documented.
- Operational acceptance checks pass.

---

## Verification Loop

Verification is required after every wave.

### Wave-by-wave checks
- **After Wave 1:**
  - build frontend
  - verify no hardcoded localhost URL in production code paths
  - confirm `.env.local` dev flow
- **After Wave 2:**
  - start backend with production env
  - confirm strict CORS
  - confirm `/health` dependency status
- **After Wave 3:**
  - `docker compose up -d`
  - restart containers and confirm data persistence
  - run backup and inspect generated snapshot artifacts
- **After Wave 4:**
  - `curl -I https://.../api/v1/health`
  - `curl -N https://.../api/v1/stream?...`
  - verify SSE chunks are not buffered
- **After Wave 5:**
  - full smoke test from frontend to backend
  - review logs
  - validate backup and restore documentation

### Escalation rule
If a wave fails its gate, stop, correct the issue, and re-run the relevant verification before moving forward.

---

## Acceptance Criteria

The phase is complete when all of the following are true:

1. Frontend uses `NEXT_PUBLIC_API_BASE_URL` everywhere it calls the API.
2. No production-facing code hardcodes `localhost`.
3. Backend CORS is restricted to production domains.
4. Qdrant uses the canonical `QDRANT_HOST` / `QDRANT_PORT=6334` contract with `prefer_grpc=True`.
5. `legal_articles` remains the primary retrieval collection.
6. Docker Compose persists data for SQLite and Qdrant.
7. Backups run daily and produce restorable snapshots.
8. Nginx terminates TLS and proxies `/api/*` to FastAPI.
9. SSE remains functional through the proxy with buffering disabled.
10. Secrets are injected from env/secret store and rotated before go-live.
11. `/health` reports real dependency health.
12. Structured logs and basic monitoring are available.
13. End-to-end production request flow is verified.

---

## Risks and Checks

### Known risks
- A hidden localhost reference may remain in an uninspected frontend component.
- CORS may be permissive in one code path and strict in another.
- SSE buffering can appear to work in dev but fail under Nginx.
- Health checks can report green even when dependencies are down unless they are real checks.
- Backup scripts can succeed syntactically but fail to capture Qdrant state if the snapshot method is wrong.

### Required checks before go-live
- Audit all frontend API calls.
- Audit environment variable defaults in backend startup.
- Confirm Qdrant startup and retrieval logs point to the same host and port.
- Confirm Nginx config includes an SSE-specific location block.
- Confirm backup retention and restore procedure are documented.

---

## Suggested Implementation Order

1. Frontend env-driven base URL.
2. Backend CORS and startup validation.
3. Compose volumes and health checks.
4. Nginx + TLS + SSE proxying.
5. Backup/restore scripts.
6. Structured logging + health check hardening.
7. EC2 deployment and Vercel deployment.
8. Full smoke tests and runbook.

---

## Handoff Notes for Execution

- Keep changes minimal and isolated per wave.
- Prefer small, reversible edits.
- If a file is used in both local dev and production, preserve local usability while hardening production defaults.
- Treat `09-CONTEXT.md` as the source of truth for locked decisions.

---

*Phase 9 plan ready for execution.*

