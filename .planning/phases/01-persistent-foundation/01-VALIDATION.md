---
phase: 1
slug: persistent-foundation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-24
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | python/pytest (minimal script verification) |
| **Config file** | none |
| **Quick run command** | `.venv\Scripts\python.exe tests/verify_phase_1.py` |
| **Full suite command** | `.venv\Scripts\python.exe tests/verify_phase_1.py` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv\Scripts\python.exe tests/verify_phase_1.py`
- **After every plan wave:** Full suite green
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | INF-03 | — | Container persists data to local volume | integration | `docker ps` | ✅ | ✅ green |
| 1-02-01 | 02 | 1 | INF-01 | — | FTS5 handles Vietnamese diacritics correctly | unit | `.venv\Scripts\python.exe tests/verify_phase_1.py` | ✅ | ✅ green |
| 1-02-03 | 02 | 1 | INF-02 | — | BaseEmbedder can be extended and run async | unit | `.venv\Scripts\python.exe tests/verify_phase_1.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/verify_phase_1.py` — created to verify core infrastructure and database layers.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| .env safety | API-03 | Privacy | Manually verify that no secrets are committed to Git. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-24
