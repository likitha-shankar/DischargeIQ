"""
Tests the RESTRICTED_DATA_MODE gate in utils/llm_client.py.

The gate exists to keep data held under a use agreement (MIMIC-IV-Note and
other PhysioNet credentialed datasets) off third-party LLM APIs. Every path
that resolves a provider into a client must be covered, including the automatic
cross-provider failover - that one fires on a timeout or a 429 with no human in
the loop, so an unguarded fallback would leak data without anyone acting.

See docs/MIMIC_CREDENTIALING.md for the policy these tests encode.
"""

import pytest

from dischargeiq.utils.llm_client import (
    enforce_restricted_data_policy,
    get_fallback_client,
    get_llm_client,
    get_native_agent_client,
    restricted_data_mode,
)

# Providers that reach a third party, and so must be refused in restricted mode.
_THIRD_PARTY_PROVIDERS = ["gemini", "anthropic", "openai", "openrouter"]


@pytest.fixture
def restricted(monkeypatch):
    """Turns on RESTRICTED_DATA_MODE for the duration of one test."""
    monkeypatch.setenv("RESTRICTED_DATA_MODE", "1")


def test_mode_off_by_default(monkeypatch):
    """The gate must not affect normal synthetic-corpus runs."""
    monkeypatch.delenv("RESTRICTED_DATA_MODE", raising=False)
    assert restricted_data_mode() is False
    # No exception: any provider is fine when the mode is off.
    for provider in _THIRD_PARTY_PROVIDERS:
        enforce_restricted_data_policy(provider)


@pytest.mark.parametrize("provider", _THIRD_PARTY_PROVIDERS)
def test_third_party_providers_blocked(restricted, provider):
    """Restricted mode refuses every provider that leaves our control."""
    with pytest.raises(ValueError, match="RESTRICTED_DATA_MODE"):
        enforce_restricted_data_policy(provider)


@pytest.mark.parametrize("provider", ["vertex", "ollama"])
def test_compliant_providers_allowed(restricted, provider):
    """Vertex (BAA) and Ollama (local) stay usable in restricted mode."""
    enforce_restricted_data_policy(provider)


def test_get_llm_client_blocked(restricted, monkeypatch):
    """The primary client path is gated before any client is constructed."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-real")
    with pytest.raises(ValueError, match="RESTRICTED_DATA_MODE"):
        get_llm_client()


def test_native_agent_client_blocked(restricted, monkeypatch):
    """Agents 3-5 take a separate anthropic branch that needs its own gate."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with pytest.raises(ValueError, match="RESTRICTED_DATA_MODE"):
        get_native_agent_client("anthropic")


def test_fallback_client_blocked(restricted, monkeypatch):
    """
    The failover path is the one that leaks without anyone acting.

    LLM_FALLBACK_PROVIDER defaults to anthropic, and a 429 on the primary
    routes calls straight to it, so this must raise rather than return a
    usable third-party client.
    """
    monkeypatch.delenv("LLM_FALLBACK_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with pytest.raises(ValueError, match="fallback provider"):
        get_fallback_client()


def test_fallback_disabled_is_still_fine(restricted, monkeypatch):
    """Explicitly disabling failover is the documented restricted-mode config."""
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "none")
    assert get_fallback_client() is None
