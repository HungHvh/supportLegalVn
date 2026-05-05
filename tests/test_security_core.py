import pytest
import asyncio
import time
from fastapi import HTTPException
from core.security import RateLimiter, CircuitBreaker

def test_rate_limiter_logic():
    limiter = RateLimiter(default_limit=2)
    
    # First two should pass
    assert limiter.check("user1") is True
    assert limiter.check("user1") is True
    
    # Third should fail
    with pytest.raises(HTTPException) as exc:
        limiter.check("user1")
    assert exc.value.status_code == 429

def test_circuit_breaker_logic():
    breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)
    
    async def failing_func():
        raise ValueError("Fail")
    
    async def success_func():
        return "OK"
    
    # First failure
    with pytest.raises(ValueError):
        asyncio.run(breaker.call(failing_func))
    assert breaker.state == "CLOSED"
    assert breaker.failure_count == 1
    
    # Second failure -> OPEN
    with pytest.raises(ValueError):
        asyncio.run(breaker.call(failing_func))
    assert breaker.state == "OPEN"
    
    # Next call should be blocked immediately (HTTP 503)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(breaker.call(success_func))
    assert exc.value.status_code == 503
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Should move to HALF-OPEN and try the success func
    result = asyncio.run(breaker.call(success_func))
    assert result == "OK"
    assert breaker.state == "CLOSED"
    assert breaker.failure_count == 0

@pytest.mark.asyncio
async def test_circuit_breaker_streaming():
    breaker = CircuitBreaker(name="test-stream", failure_threshold=1)
    
    async def failing_gen():
        yield "start"
        raise ValueError("Fail")
        yield "end"

    # Trigger failure
    with pytest.raises(ValueError):
        async for chunk in breaker.astream_call(failing_gen):
            pass
    
    assert breaker.state == "OPEN"
    
    # Blocked
    with pytest.raises(HTTPException) as exc:
        async for chunk in breaker.astream_call(failing_gen):
            pass
    assert exc.value.status_code == 503
