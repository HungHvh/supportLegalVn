---
phase: 3
slug: smart-retrieval-rag
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-26
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/test_retrieval.py` |
| **Full suite command** | `pytest tests/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_retrieval.py`
- **After every plan wave:** Run `pytest tests/`
- **Before /gsd-verify-work:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | CLS-01 | — | N/A | unit | `pytest tests/test_classifier.py` | ✅ Yes | ✅ green |
| 03-01-02 | 01 | 1 | CLS-02 | — | N/A | unit | `pytest tests/test_classifier.py` | ✅ Yes | ✅ green |
| 03-01-03 | 01 | 2 | RAG-01 | — | N/A | integration | `pytest tests/test_retrieval.py` | ✅ Yes | ✅ green |
| 03-02-01 | 02 | 1 | RAG-02 | — | N/A | integration | `pytest tests/test_retrieval.py` | ✅ Yes | ✅ green |
| 03-02-02 | 02 | 2 | RAG-03 | — | N/A | integration | `pytest tests/test_generation.py` | ✅ Yes | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_classifier.py` — stubs for CLS-01, CLS-02
- [ ] `tests/test_retrieval.py` — stubs for RAG-01, RAG-02
- [ ] `tests/test_generation.py` — stubs for RAG-03
- [ ] `pip install pytest pytest-asyncio` — ensure test framework is present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Response Tone Consistency | RAG-03 | Subjective quality | Run a set of 5 sample queries and verify the IRAC tone manually. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** ✅ approved

## Validation Audit 2026-04-26
| Metric | Count |
|--------|-------|
| Gaps found | 3 (test stubs missing os import or missing files) |
| Resolved | 3 (created test_generation.py, fixed imports, configured embedding model) |
| Escalated | 0 |
| Nyquist Compliant | true |
