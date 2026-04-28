"""
File: conftest.py
Owner: Deepesh Kumar Appar Senthilkumar
Description: Root pytest configuration shared by all test directories.
  Provides an autouse rate-limiter fixture that enforces a minimum gap between
  consecutive ``@pytest.mark.slow`` tests to stay within Anthropic free-tier
  rate limits (5 RPM, 10k input tokens/min).
  Without this, running the full slow suite in sequence saturates the account
  limit and produces cascading 429 RateLimitError failures.
Dependencies: pytest, time (stdlib)
Usage: automatically loaded by pytest when running from the repo root.
"""

from __future__ import annotations

import time

import pytest

# Minimum seconds between consecutive slow-test API calls.
# Anthropic free tier limits: 5 RPM (requires 12 s) and 10,000 input tokens/min.
# Agent 1 (extraction) has a ~4,700-token system prompt, making each call ~5,300
# input tokens. To stay under 10k tokens/min: 60 / 35 ≈ 1.7 calls/min × 5,300
# = 9,010 tokens/min. 35 s provides a safe margin for all agent types.
_SLOW_CALL_GAP_SECONDS = 35.0


@pytest.fixture(scope="session")
def _slow_test_state() -> dict:
    """
    Session-scoped mutable dict that tracks when the last slow test completed.

    Shared across all test files via the root conftest so the rate-limit
    budget is respected even when tests live in different directories.

    Returns:
        dict: Single key ``last_call_at`` (float, monotonic clock, default 0.0).
    """
    return {"last_call_at": 0.0}


@pytest.fixture(autouse=True)
def _rate_limit_slow_tests(request, _slow_test_state: dict) -> None:
    """
    Enforce a minimum inter-test delay for every slow-marked test.

    Sleeps at setup time so the API call inside the upcoming test is at least
    ``_SLOW_CALL_GAP_SECONDS`` after the previous slow test completed.
    Records the completion time at teardown so the next fixture invocation can
    measure the correct elapsed duration.

    No-op for tests that are not marked ``@pytest.mark.slow``.

    Args:
        request: Pytest FixtureRequest — used to check the slow marker.
        _slow_test_state: Session-scoped dict with ``last_call_at`` timestamp.
    """
    if not request.node.get_closest_marker("slow"):
        yield
        return

    elapsed = time.monotonic() - _slow_test_state["last_call_at"]
    wait = _SLOW_CALL_GAP_SECONDS - elapsed
    if wait > 0:
        time.sleep(wait)

    yield  # test body runs here

    # Record completion so the next slow test measures from the right baseline.
    _slow_test_state["last_call_at"] = time.monotonic()
