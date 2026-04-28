# Phase 6.3: Groq (Llama-3) Classifier Provider

## Objective
Integrate Groq as the primary classifier provider to achieve extreme low latency (< 1s) for pre-query classification.

## Requirements
- [x] Implement `GroqClient` in `tools/groq_client.py`.
- [x] Update `LegalQueryClassifier` in `core/classifier.py` to support `groq` provider.
- [x] Configure `GROQ_API_KEY` in `.env`.
- [x] Verify latency and accuracy with Llama-3 8B.

## Technical Design
- Use `AsyncOpenAI` client (via `openai` package) or `httpx` for Groq API calls.
- Groq is OpenAI-compatible: `base_url="https://api.groq.com/openai/v1"`.
- Default model: `llama-3.1-8b-instant` (replacing deprecated `llama3-8b-8192`).

## Debugging Notes
- Fixed `.env` corruption (UTF-16/null character issue).
- Resolved `400 Bad Request` by switching to a supported production model.

## Verification Plan
- [x] Unit test for `GroqClient`.
- [x] Integration test with `LegalQueryClassifier`.
- [x] Latency benchmarking.
