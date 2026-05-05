# Context: Phase 17 - API Gateway Layer

## Domain Boundary
Implementation of API protection mechanisms including Rate Limiting and Circuit Breaking to ensure system stability and cost control.

## Locked Decisions

### 1. Storage & Library
- **Library**: `cachetools` (specifically `TTLCache`).
- **Mechanism**: In-memory storage. No external Redis requirement to keep the stack lightweight.

### 2. Rate Limiting Strategy
- **Pattern**: FastAPI **Dependencies**.
- **IP-based**: 10 requests per minute (Sliding window via `TTLCache`).
- **User-based**: Supported using the same `cachetools` logic.
- **Granularity**: 
    - `/ask` and `/stream`: Shared strict limit.
    - `/search`: Separate, more relaxed limit.

### 3. Circuit Breaker
- **Implementation**: Custom lightweight class (no external `pybreaker`).
- **Scope**: Applied to **LLM Service Calls** (Classifier, Generator).
- **Behavior**: 
    - Monitor failure rates.
    - "Open" circuit on threshold breach to return immediate "System Busy" errors.
    - "Half-open" state for periodic recovery testing.

### 4. Error Feedback
- **Response**: Return descriptive error messages to the user.
- **Status Codes**: 429 for Rate Limit, 503 for Circuit Breaker.

## Canonical Refs
- `api/v1/endpoints.py`: Integration point for FastAPI dependencies.
- `core/config.py`: Configuration for limit thresholds.
- `core/security.py` (New): Proposed home for RateLimiter and CircuitBreaker logic.

## Codebase Context
- Current RAG pipeline calls LLMs directly.
- No existing rate limiting logic in the codebase.
