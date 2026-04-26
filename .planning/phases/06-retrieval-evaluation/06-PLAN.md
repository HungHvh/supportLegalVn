# Phase 6 Plan: Retrieval Evaluation

## 📝 Overview
This plan implements a robust evaluation pipeline to compare the Phase 5 "Optimized" RAG system against a "Baseline" version. We will generate a golden dataset of legal queries and use Ragas with Gemini-2.0-Flash to score retrieval and generation quality.

## 🏗 Tasks

### 1. Environment & Dependencies
- [x] Install required libraries: `ragas`, `langchain-google-genai`, `pandas`, `tabulate`.
- [x] Verify `GOOGLE_API_KEY` is correctly set in `.env`.
- [x] Use Docker for execution to bypass local DLL issues (`torch`, `spacy`, `onnxruntime`).

### 2. Synthetic Dataset Generation
- [x] Create `scripts/generate_eval_data.py`.
- [x] Run generation in Docker: `docker-compose run api python scripts/generate_eval_data.py`
- [x] Generate ~20 synthetic triplets for POC.
- [x] Save to `.planning/phases/06-retrieval-evaluation/golden_set_synthetic.json`.

### 3. Manual Edge Case Curation
- [x] Create `.planning/phases/06-retrieval-evaluation/golden_set_manual.json`.
- [x] Define initial set of high-difficulty questions (Law 2014 vs 2020).

### 4. Ablation Runner Implementation
- [x] Update `core/rag_pipeline.py` with ablation toggles.
- [x] Create `scripts/run_benchmarks.py`.
- [x] Run benchmarks in Docker: `docker-compose run api python scripts/run_benchmarks.py`

### 5. Ragas Scoring & Reporting
- [x] Implement scoring logic in `scripts/run_benchmarks.py`.
- [x] Generate `eval_report.md` and `eval_results.csv`.

## ✅ Verification Loop

### UAT-06-01: Dataset Quality
- [x] Verify synthetic samples for legal accuracy.

### UAT-06-02: Pipeline Comparison
- [x] Confirm "Baseline" vs "Optimized" return different nodes.

### UAT-06-03: Final Report
- [x] Verify `eval_report.md` contains the comparison table.
