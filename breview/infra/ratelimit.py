"""Rate limiting and circuit breaker for external API calls."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls.

    Args:
        max_calls: Maximum number of calls in the time window
        period: Time window in seconds
    """

    def __init__(self, max_calls: int = 60, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a rate limit slot is available."""
        async with self._lock:
            now = time.monotonic()
            # Remove expired entries
            self._calls = [t for t in self._calls if now - t < self.period]

            if len(self._calls) >= self.max_calls:
                # Calculate wait time
                oldest = self._calls[0]
                wait_time = self.period - (now - oldest)
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                # Clean up again after waiting
                now = time.monotonic()
                self._calls = [t for t in self._calls if now - t < self.period]

            self._calls.append(time.monotonic())


class CircuitBreaker:
    """Circuit breaker pattern for external service calls.

    States:
    - CLOSED: Normal operation, calls go through
    - OPEN: Too many failures, calls are blocked
    - HALF_OPEN: Testing if service recovered

    Args:
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds to wait before trying again
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> str:
        """Current circuit breaker state."""
        if self._state == self.OPEN:
            if self._last_failure_time:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        """Record a successful call."""
        self._failure_count = 0
        self._state = self.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures. "
                f"Will retry in {self.recovery_timeout}s"
            )

    def allow_request(self) -> bool:
        """Check if a request is allowed."""
        state = self.state
        if state == self.CLOSED:
            return True
        if state == self.HALF_OPEN:
            logger.info("Circuit breaker half-open, allowing test request")
            return True
        return False
