# Phase 9 Summary: Production Deployment & Infrastructure

**Status:** Complete
**Date:** 2026-05-06

## What changed

### Frontend deployment hardening
- Updated `frontend/src/lib/apiBaseUrl.ts` so production requires `NEXT_PUBLIC_API_BASE_URL` instead of silently falling back to localhost.
- Explicitly surfaced `NEXT_PUBLIC_API_BASE_URL` in `frontend/next.config.ts`.
- Updated `frontend/README.md` with local `.env.local` guidance and production Vercel deployment notes.

### Backend production contract
- Tightened production validation in `app.py`:
  - `QDRANT_HOST` is required
  - `QDRANT_PORT` must be `6334`
  - `ALLOWED_ORIGINS` must be set
  - provider secrets are still validated
- Added a lightweight JSON logging baseline with optional production file logging via `LOG_FILE_PATH`.
- Updated `.env.example` to document production-friendly environment variables.

### Deployment assets
- Added `deploy/nginx/supportlegal.conf` with:
  - HTTPS redirect
  - `/api/*` proxying
  - SSE-safe `/api/v1/stream` settings with `proxy_buffering off`
- Added `deploy/setup_ec2.sh` for EC2 bootstrap.
- Added backup and restore scripts:
  - `scripts/backup_legal_data.sh`
  - `scripts/restore_legal_data.sh`
- Added `deploy/README.md` runbook guidance.

### Repository hygiene
- Updated `.gitignore` to ignore `.env.local`, `.env.*.local`, and generated `backups/` directories.

## Validation
- `npm run build` in `frontend/` ✅
- Direct Python startup validation for production env handling ✅
- Direct validation of missing `QDRANT_PORT` failure path ✅

## Notes
- `pytest` in this Windows environment hits a native access-violation in transitive dependencies (`pyarrow` / `onnxruntime` / `qdrant_client`) before the phase-specific checks can complete. The new Phase 9 logic itself validated successfully via direct startup checks and the frontend build passed.

