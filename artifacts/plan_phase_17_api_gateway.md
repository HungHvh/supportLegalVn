# Plan: Phase 17 - API Gateway Layer (Bảo vệ API & Rate Limit)

## 🎯 Goal
Protect the legal RAG system from abuse, DDoS, and spam while ensuring high availability during LLM provider failures.

## 🏗️ Architecture
- **Layer**: FastAPI Dependencies.
- **Backend Storage**: In-memory via `cachetools` (specifically `TTLCache`).
- **Patterns**: Sliding Window Log / Token Bucket, Custom Circuit Breaker.

## 📋 Features

### 1. Rate Limiting (Tiered)
- **IP-based Limit**:
    - **Target**: Anonymous/All requests.
    - **Default**: 10 requests/minute per IP.
- **User-based Limit**:
    - **Target**: Authenticated users (via X-User-ID or API Key).
- **Endpoint Specific**:
    - Separate limits for Chat (`/ask`, `/stream`) vs Search (`/search`).

### 2. Circuit Breaker (Cầu dao tự động)
- **Implementation**: Custom lightweight Python class.
- **Monitoring**: Watch for 5xx errors or timeouts from LLM providers (Groq, Gemini, DeepSeek).
- **Behavior**: 
    - Threshold-based state transitions (Closed -> Open -> Half-Open).
    - Return 503 "System Busy" error when Open.

### 3. Core Security Module
- Implement a `RateLimiter` and `CircuitBreaker` utility in `core/security.py`.

## 🛠️ Implementation Steps

### Wave 1: Rate Limiting Foundation
1.  **Add Dependency**: Add `cachetools` to `requirements.txt`.
2.  **Security Module**: Implement `core/security.py` with `RateLimiter` class using `TTLCache`.
3.  **FastAPI Dependencies**: Create rate limit dependencies in `api/dependencies.py` or `api/v1/endpoints.py`.

### Wave 2: Circuit Breaker & Integration
1.  **Circuit Breaker Logic**: Implement `CircuitBreaker` class in `core/security.py`.
2.  **LLM Wrapper**: Wrap LLM provider calls with the Circuit Breaker.
3.  **Endpoint Integration**: Apply dependencies to `/ask`, `/stream`, and `/search`.

### Wave 3: Testing & Validation
1.  **Unit Tests**: Verify rate limit counting and window reset.
2.  **Simulation**: Mock LLM failures to verify Circuit Breaker transitions.
3.  **Load Test**: Verify system returns 429/503 under stress.

### Wave 3: Testing & Validation
1.  **Load Test**: Use Locust to verify rate limits trigger correctly.
2.  **Simulation**: Mock LLM failures to verify the Circuit Breaker opens/closes.
3.  **Dashboard/Logs**: Ensure blocked requests are logged for monitoring.

## ✅ Acceptance Criteria
- [ ] Requests exceeding 10/min per IP receive HTTP 429.
- [ ] LLM provider failures trigger Circuit Breaker after N attempts.
- [ ] Redis is used as the primary store for rate limit counters.
- [ ] System returns descriptive "System Busy" or "Too Many Requests" messages.

## 📅 Timeline
- **Estimated Effort**: 3-4 days.
- **Priority**: High (System Stability).
