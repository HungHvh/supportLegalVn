# Plan: Phase 17 - API Gateway Layer

## 🎯 Goal
Protect the legal RAG system from abuse and provider failures using in-memory rate limiting and a custom circuit breaker.

## 🏗️ Waves & Tasks

### Wave 1: Core Security Utilities
| Task | Description | Files Modified |
| :--- | :--- | :--- |
| **1.1** | Add `cachetools` to project dependencies. | `requirements.txt` |
| **1.2** | Implement `RateLimiter` utility in `core/security.py` using `TTLCache`. Support IP-based and User-based identification. | `core/security.py` |
| **1.3** | Implement `CircuitBreaker` class in `core/security.py` to track failure rates and manage Open/Closed/Half-Open states. | `core/security.py` |

### Wave 2: API & Pipeline Integration
| Task | Description | Files Modified |
| :--- | :--- | :--- |
| **2.1** | Define FastAPI dependencies for `ask_rate_limit` (shared by ask/stream) and `search_rate_limit` in `api/dependencies.py`. | `api/dependencies.py` |
| **2.2** | Apply Rate Limit dependencies to `/ask`, `/stream`, and `/search-articles` endpoints. | `api/v1/endpoints.py` |
| **2.3** | Wrap LLM generation and classification calls in `core/rag_pipeline.py` with the `CircuitBreaker`. | `core/rag_pipeline.py` |

### Wave 3: Validation & Handoff
| Task | Description | Files Modified |
| :--- | :--- | :--- |
| **3.1** | Create a test script `tests/test_api_protection.py` to verify Rate Limit triggers (429) and Circuit Breaker opens (503) on mocked failures. | `tests/test_api_protection.py` |
| **3.2** | Perform final verification and update `STATE.md`. | `STATE.md` |

---

## 🛠️ Task Details

### Task 1.1: Add Dependencies
- **Action**: Add `cachetools==5.3.3` (or latest) to `requirements.txt`.
- **Acceptance Criteria**: `pip install -r requirements.txt` succeeds and `cachetools` is available in the environment.

### Task 1.2: RateLimiter Implementation
- **Action**: Use the user-provided `TTLCache` logic. Expand it to a class that can handle multiple "buckets" (e.g., one for IPs, one for Users).
- **Read First**: `c:/Users/hvcng/PycharmProjects/supportLegalVn/core/rag_pipeline.py` (for context on how it might be called).
- **Acceptance Criteria**: `core/security.py` exists and contains a `RateLimiter` class that raises `HTTPException(429)` when limits are exceeded.

### Task 1.3: CircuitBreaker Implementation
- **Action**: Implement a simple state machine:
    - **Closed**: Requests pass through. Failures increment a counter.
    - **Open**: Requests fail immediately with `503`. Moves to Half-Open after a timeout.
    - **Half-Open**: Allows one request to test the provider.
- **Acceptance Criteria**: `CircuitBreaker` class handles state transitions correctly based on failure thresholds.

### Task 2.1: FastAPI Dependencies
- **Action**: Create `api/dependencies.py`. Implement functions that extract the client IP or a user ID from headers and call the `RateLimiter`.
- **Acceptance Criteria**: Dependency functions are ready to be used in FastAPI routes.

### Task 2.2: Endpoint Integration
- **Action**: Update `router.post("/ask")`, `router.post("/stream")`, and `router.post("/search-articles")` to use the new dependencies.
- **Read First**: `api/v1/endpoints.py`.
- **Acceptance Criteria**: Endpoints return `429` when calling them too rapidly.

### Task 2.3: Pipeline Protection
- **Action**: Initialize a global `CircuitBreaker` instance for LLM calls. Wrap `self.client.generate_content_async` and `self.retriever.classifier.classify` calls.
- **Read First**: `core/rag_pipeline.py`.
- **Acceptance Criteria**: LLM provider timeouts or 5xx errors trigger the circuit breaker.

---

## 🏁 Verification Strategy
1.  **Rate Limit Test**: Script that calls `/ask` 11 times in 1 second; 11th call must return 429.
2.  **Circuit Breaker Test**: Mock the LLM client to throw `Exception` 5 times; 6th call must return 503 immediately without calling the mock.
