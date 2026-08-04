"""
File: dischargeiq/tests/conftest.py
Owner: Likitha Shankar
Description: Shared pytest fixtures. Resets process-global state before and
  after every test: the quota-429 cooldown in llm_client (a leaked cooldown
  silently reroutes later tests to the fallback provider) and the
  document-hash pipeline result cache in session_store (a leaked entry
  serves one test's result to another test using the same input text).
Dependencies: pytest, dischargeiq.utils.llm_client, dischargeiq.services.session
Called by: pytest (auto-discovered).
"""

import pytest

from dischargeiq.api import middleware
from dischargeiq.api.routes import media
from dischargeiq.services.session import session_store
from dischargeiq.utils import llm_client


def _clear_global_state() -> None:
    """Reset every process-global cache/cooldown tests can pollute."""
    llm_client._quota_cooldown_until.clear()
    with session_store._result_lock:
        session_store._result_by_hash.clear()
    with media._audio_cache_lock:
        media._audio_cache.clear()
    # Rate-limit windows are keyed by path+IP, and every TestClient shares the
    # IP "testclient". Without this, requests made by one test count against
    # the next one's budget - a test that legitimately calls /analyze/text a
    # few times can push an unrelated later test over the 5/60s limit and
    # fail it with a 429 that has nothing to do with what it asserts.
    with middleware._rate_lock:
        middleware._rate_windows.clear()


@pytest.fixture(autouse=True)
def _reset_cross_test_state():
    """
    Clear process-global state that would otherwise leak between tests:
    provider quota cooldowns (would reroute later tests to the fallback),
    the document-hash result cache (would serve one test's pipeline result
    to another test reusing the same input text), and the per-case audio
    cache (would answer 200 where a test forces a generation failure).
    """
    _clear_global_state()
    yield
    _clear_global_state()
