"""Degradation manager - handles graceful degradation when LLM is unavailable."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DegradationMode(str, Enum):
    """Degradation modes."""

    FULL = "full"  # Full LLM review
    LINTER_ONLY = "linter_only"  # Linter only, no LLM
    STATIC_ONLY = "static_only"  # Static checks only


class DegradationManager:
    """Manages graceful degradation when LLM services are unavailable.

    When LLM API is unavailable, the system degrades to linter-only mode
    instead of failing completely.
    """

    def __init__(self):
        self._mode = DegradationMode.FULL
        self._llm_failures = 0
        self._failure_threshold = 3

    @property
    def mode(self) -> DegradationMode:
        """Current degradation mode."""
        return self._mode

    @property
    def is_degraded(self) -> bool:
        """Whether we're in degraded mode."""
        return self._mode != DegradationMode.FULL

    def record_llm_failure(self, error: Exception) -> None:
        """Record an LLM failure."""
        self._llm_failures += 1
        logger.warning(f"LLM failure #{self._llm_failures}: {error}")

        if self._llm_failures >= self._failure_threshold:
            self._mode = DegradationMode.LINTER_ONLY
            logger.warning(f"Degraded to {self._mode.value} mode after {self._llm_failures} failures")

    def record_llm_success(self) -> None:
        """Record a successful LLM call."""
        if self._llm_failures > 0:
            self._llm_failures = max(0, self._llm_failures - 1)
            if self._llm_failures == 0 and self._mode != DegradationMode.FULL:
                self._mode = DegradationMode.FULL
                logger.info("Restored to full mode after successful LLM calls")

    def check_llm_availability(self, llm_client: Any) -> bool:
        """Check if LLM is available by making a lightweight call.

        Args:
            llm_client: LLM client to test

        Returns:
            True if LLM is available
        """
        try:
            # Try a minimal completion to check availability
            import asyncio

            async def _test():
                response = await llm_client.complete(
                    messages=[{"role": "user", "content": "ping"}],
                    model="gpt-4",
                    max_tokens=1,
                )
                return True

            # Run with timeout
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(asyncio.wait_for(_test(), timeout=10))
            self.record_llm_success()
            return result
        except Exception as e:
            self.record_llm_failure(e)
            return False

    def execute_with_fallback(
        self,
        llm_func: Callable,
        linter_func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute with fallback to linter if LLM fails.

        Args:
            llm_func: Function to call for LLM review
            linter_func: Function to call for linter-only review
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            Result from either function
        """
        if self._mode == DegradationMode.LINTER_ONLY:
            logger.info("In degraded mode, using linter-only")
            return linter_func(*args, **kwargs)

        try:
            result = llm_func(*args, **kwargs)
            self.record_llm_success()
            return result
        except Exception as e:
            self.record_llm_failure(e)
            logger.warning(f"LLM failed, falling back to linter: {e}")
            return linter_func(*args, **kwargs)

    def reset(self) -> None:
        """Reset to full mode."""
        self._mode = DegradationMode.FULL
        self._llm_failures = 0
