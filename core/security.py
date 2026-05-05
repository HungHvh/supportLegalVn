import time
import logging
from typing import Dict, Any, Optional, Callable, Awaitable, AsyncGenerator
from fastapi import HTTPException
from cachetools import TTLCache

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    In-memory Rate Limiter using cachetools TTLCache.
    Supports tiered limiting for different identifiers (IP, User ID, etc).
    """
    def __init__(self, maxsize: int = 10000, ttl: int = 60, default_limit: int = 10):
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.default_limit = default_limit

    def check(self, identifier: str, limit: Optional[int] = None) -> bool:
        """
        Check if the identifier has exceeded the limit.
        Raises HTTPException(429) if limit exceeded.
        """
        current_limit = limit if limit is not None else self.default_limit
        current_time = time.time()

        if identifier not in self.cache:
            self.cache[identifier] = {"count": 1, "start_time": current_time}
            return True

        data = self.cache[identifier]
        if data["count"] >= current_limit:
            logger.warning(f"Rate limit exceeded for {identifier}: {data['count']}/{current_limit}")
            raise HTTPException(
                status_code=429, 
                detail={
                    "error": "Too Many Requests",
                    "message": "Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau một lát.",
                    "limit": current_limit,
                    "retry_after": int(self.cache.ttl - (current_time - data["start_time"]))
                }
            )

        data["count"] += 1
        # Re-assign to update TTL and internal state if needed
        self.cache[identifier] = data
        return True

class CircuitBreaker:
    """
    Lightweight Circuit Breaker to protect external LLM calls.
    States: CLOSED, OPEN, HALF_OPEN
    """
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF-OPEN"

    def __init__(
        self, 
        name: str, 
        failure_threshold: int = 5, 
        recovery_timeout: int = 60
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def call(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Wrap an async function call with circuit breaker logic.
        """
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info(f"Circuit Breaker [{self.name}] moving to HALF-OPEN")
                self.state = self.HALF_OPEN
            else:
                logger.error(f"Circuit Breaker [{self.name}] is OPEN. Blocking request.")
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Service Unavailable",
                        "message": "Hệ thống đang bận hoặc nhà cung cấp AI đang gặp sự cố. Vui lòng thử lại sau ít phút."
                    }
                )

        try:
            result = await func(*args, **kwargs)
            
            # If we reach here, the call succeeded
            if self.state == self.HALF_OPEN:
                logger.info(f"Circuit Breaker [{self.name}] moving to CLOSED (Recovered)")
                self.state = self.CLOSED
                self.failure_count = 0
            
            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            logger.error(f"Circuit Breaker [{self.name}] failure {self.failure_count}/{self.failure_threshold}: {str(e)}")

            if self.failure_count >= self.failure_threshold:
                logger.critical(f"Circuit Breaker [{self.name}] moving to OPEN")
                self.state = self.OPEN
            
            raise e

    async def astream_call(self, func: Callable[..., AsyncGenerator[Any, None]], *args, **kwargs) -> AsyncGenerator[Any, None]:
        """
        Wrap an async generator call with circuit breaker logic.
        """
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info(f"Circuit Breaker [{self.name}] moving to HALF-OPEN")
                self.state = self.HALF_OPEN
            else:
                logger.error(f"Circuit Breaker [{self.name}] is OPEN. Blocking request.")
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Service Unavailable",
                        "message": "Hệ thống đang bận hoặc nhà cung cấp AI đang gặp sự cố. Vui lòng thử lại sau ít phút."
                    }
                )

        try:
            # We wrap the generator iteration
            async for chunk in func(*args, **kwargs):
                if self.state == self.HALF_OPEN:
                    logger.info(f"Circuit Breaker [{self.name}] moving to CLOSED (Recovered)")
                    self.state = self.CLOSED
                    self.failure_count = 0
                yield chunk

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            logger.error(f"Circuit Breaker [{self.name}] failure {self.failure_count}/{self.failure_threshold}: {str(e)}")

            if self.failure_count >= self.failure_threshold:
                logger.critical(f"Circuit Breaker [{self.name}] moving to OPEN")
                self.state = self.OPEN
            
            raise e

# Global instances
rate_limiter = RateLimiter()
llm_circuit_breaker = CircuitBreaker(name="LLM-Provider")
