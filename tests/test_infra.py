"""Tests for infrastructure modules: exemptions, audit, rate limiter."""

import asyncio
import time

import pytest
from pathlib import Path

from breview.infra.exemption import ExemptionChecker, ExemptionConfig
from breview.infra.ratelimit import RateLimiter, CircuitBreaker


class TestExemptionChecker:
    """Tests for the exemption checker."""

    def setup_method(self):
        self.checker = ExemptionChecker()

    def test_file_pattern_match(self):
        assert self.checker.is_file_exempt("src/generated.pb.cc")
        assert self.checker.is_file_exempt("vendor/some_lib/main.py")
        assert self.checker.is_file_exempt("third_party/dep/lib.h")

    def test_file_pattern_no_match(self):
        assert not self.checker.is_file_exempt("src/main.py")
        assert not self.checker.is_file_exempt("lib/utils.cpp")

    def test_custom_patterns(self):
        config = ExemptionConfig(file_patterns=["*.log", "build/**"])
        checker = ExemptionChecker(config)
        assert checker.is_file_exempt("app.log")
        assert checker.is_file_exempt("build/output.so")
        assert not checker.is_file_exempt("src/main.py")

    def test_line_exemption(self):
        assert self.checker.is_line_exempt("x = 1  # breview: ignore")
        assert not self.checker.is_line_exempt("x = 1")

    def test_pr_exemption(self):
        assert self.checker.is_pr_exempt("Auto-generated PR. breview: skip")
        assert not self.checker.is_pr_exempt("Fix bug in parser")


class TestRateLimiter:
    """Tests for the rate limiter."""

    @pytest.mark.asyncio
    async def test_within_limit(self):
        limiter = RateLimiter(max_calls=5, period=1.0)
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_exceeds_limit(self):
        limiter = RateLimiter(max_calls=2, period=0.1)
        await limiter.acquire()
        await limiter.acquire()
        # Third call should wait
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # Should have waited some time


class TestCircuitBreaker:
    """Tests for the circuit breaker."""

    def test_initial_state(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

    def test_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    def test_half_open_after_timeout(self):
        import time
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN
        assert cb.allow_request() is True
