---
status: testing
phase: 06-retrieval-evaluation
source:
  - .planning/phases/06-retrieval-evaluation/06-SUMMARY.md
started: 2026-04-27T14:42:00+07:00
updated: 2026-04-27T14:42:00+07:00
---

## Current Test

number: 1
name: Cold Start Smoke Test
expected: |
  1. Kill any running containers: `docker compose down`.
  2. Start services: `docker compose up -d`.
  3. Verify services are running: `docker compose ps` shows `api` and `qdrant` as Up.
  4. Test health endpoint: `curl http://localhost:8000/health` (or browser) returns `{"status": "healthy"}`.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: |
  1. Kill any running containers: `docker compose down`.
  2. Start services: `docker compose up -d`.
  3. Verify services are running: `docker compose ps` shows `api` and `qdrant` as Up.
  4. Test health endpoint: `curl http://localhost:8000/health` (or browser) returns `{"status": "healthy"}`.
result: [pending]

### 2. Synthetic Data Generation (Verification)
expected: |
  Review `.planning/phases/06-retrieval-evaluation/golden_set_synthetic.json`. 
  It should contain 10 triplets with `question`, `context`, and `ground_truth` relevant to Vietnamese law.
result: [pending]

### 3. Manual Curation (Resolution 115)
expected: |
  Review `.planning/phases/06-retrieval-evaluation/golden_set_manual.json`. 
  It should contain edge cases for Vietnamese Election Law (Resolution 115/NQ-HĐBCQG) that test keyword recall (e.g., asking for specific clause numbers).
result: [pending]

### 4. Ablation Study Consistency
expected: |
  Running `python scripts/run_benchmarks.py` (simulated or actual) or reviewing the runner output shows that the "Optimized" pipeline correctly uses RRF fusion while the "Baseline" uses only vector search.
result: [pending]

### 5. Final Report Verification
expected: |
  Review `.planning/phases/06-retrieval-evaluation/eval_report.md`. 
  The report must show a clear improvement (approx +31% Hit Rate) and document the findings on keyword recall vs dense-only retrieval.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0

## Gaps

[none yet]
