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

from dischargeiq.services.session import session_store
from dischargeiq.utils import llm_client


@pytest.fixture(autouse=True)
def _reset_cross_test_state():
    """
    Clear process-global state that would otherwise leak between tests:
    provider quota cooldowns (would reroute later tests to the fallback) and
    the document-hash result cache (would serve one test's pipeline result
    to another test that reuses the same input text).
    """
    llm_client._quota_cooldown_until.clear()
    with session_store._result_lock:
        session_store._result_by_hash.clear()
    yield
    llm_client._quota_cooldown_until.clear()
    with session_store._result_lock:
        session_store._result_by_hash.clear()
