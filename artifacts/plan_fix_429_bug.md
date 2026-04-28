# Plan: Fix Gemini 429 Bug

## Problem
The Gemini 2.0 Flash API (Free Tier) frequently returns 429 Resource Exhausted errors. These are not handled, causing the RAG pipeline to fail and return 500 errors to the user.

## Root Cause
- Gemini Free Tier has strict rate limits (RPM/RPD).
- Each request to `/ask` makes 2 LLM calls (Classifier + Generator).

## Solution
1. **Implement Exponential Backoff**: Use `tenacity` to retry Gemini calls when 429 or 500 errors occur.
2. **Centralize LLM Access**: Create `tools/gemini_client.py` to wrap all Gemini interactions.
3. **Graceful Degradation**:
    - If classifier fails after retries, default to "General" domain.
    - If generator fails, return a clear "Rate limit exceeded, please try again in X seconds" message.
4. **API Optimization**:
    - Update `app.py` to handle `ResourceExhausted` specifically and return 429/503 status codes.

## Step-by-Step
1. [x] Install `tenacity`.
2. [x] Create `tools/gemini_client.py`.
3. [x] Update `core/classifier.py` to use `GeminiClient`.
4. [x] Update `core/rag_pipeline.py` to use `GeminiClient`.
5. [x] Update `app.py` exception handler.
6. [x] Verify with tests.
