"""
File: dischargeiq/utils/llm_client.py
Owner: Likitha Shankar
Description: Central LLM routing — builds an OpenAI-compatible client for anthropic,
  openrouter, openai, or ollama from LLM_PROVIDER/LLM_MODEL and validates API keys with
  clear ValueError messages. call_chat_with_fallback adds OpenRouter-only retries for
  empty completions, developer-instruction role merge, and 429 backoff.
Key functions/classes: require_provider_api_key, get_llm_client, call_chat_with_fallback
Edge cases handled:
  - OpenRouter empty content and rate limits retry with backoff; role fallback on
    unsupported developer-message errors; Ollama uses placeholder API key string.
Dependencies: openai (SDK); reads env vars only (no other dischargeiq imports).
Called by: dischargeiq.agents.extraction_agent, diagnosis_agent, patient_simulator_agent,
  dischargeiq.main (/chat), dischargeiq.tests.test_api_guardrails, test_resilience_hardening.
"""

import logging
import os
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

# Anthropic default: dated Haiku (cheapest tier). Undated aliases can 404.
# For higher-quality eval / demos, set LLM_MODEL=claude-sonnet-4-20250514 in .env.
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"

# Default configuration per provider.
# Add a new provider here — no agent code needs to change.
_PROVIDER_DEFAULTS: dict[str, dict] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "default_model": "openai/gpt-4o-mini",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "anthropic": {
        # Anthropic exposes an OpenAI-compatible chat completions endpoint at
        # /v1/. Using it keeps the shared OpenAI SDK client in this module
        # working without forcing every agent to carry a second SDK dependency.
        "base_url": "https://api.anthropic.com/v1/",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": DEFAULT_ANTHROPIC_MODEL,
    },
    "ollama": {
        # Ollama exposes an OpenAI-compatible endpoint locally.
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,  # "ollama" is used as a placeholder — no real key needed
        "default_model": "llama3.2",
    },
}


def require_provider_api_key(provider: str) -> None:
    """
    Ensure the API key env var for the chosen provider is set and non-empty.

    Raises:
        ValueError: With a human-readable message (not KeyError) when missing.
    """
    p = provider.lower()
    if p not in _PROVIDER_DEFAULTS:
        return
    env_name = _PROVIDER_DEFAULTS[p]["api_key_env"]
    if env_name is None:
        return
    raw = os.environ.get(env_name, "")
    if isinstance(raw, str):
        raw = raw.strip()
    if not raw:
        raise ValueError(
            f"Missing API key for LLM_PROVIDER={provider!r}. "
            f"Set {env_name} in your .env (see .env.example). "
            f"For Claude on all agents use LLM_PROVIDER=anthropic and "
            f"LLM_MODEL={DEFAULT_ANTHROPIC_MODEL!r}."
        )


def get_llm_client() -> tuple[OpenAI, str]:
    """
    Build an OpenAI-compatible client and resolve the model name from env vars.

    Reads LLM_PROVIDER (default: anthropic) to select the backend, then
    reads the provider-specific API key and base URL. LLM_MODEL overrides the
    provider default model when set.

    Returns:
        tuple[OpenAI, str]: Configured client and the resolved model name string.

    Raises:
        ValueError: If LLM_PROVIDER is invalid or the required API key is missing.
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()

    if provider not in _PROVIDER_DEFAULTS:
        supported = ", ".join(_PROVIDER_DEFAULTS)
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. "
            f"Supported values: {supported}"
        )

    require_provider_api_key(provider)
    config = _PROVIDER_DEFAULTS[provider]

    # Ollama does not require a real API key; pass a placeholder string so the
    # OpenAI client constructor does not reject a None value.
    if config["api_key_env"] is None:
        api_key = "ollama"
    else:
        api_key = os.environ[config["api_key_env"]].strip()

    # Allow Ollama base URL override for remote or Docker-based installs.
    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", config["base_url"])
    else:
        base_url = config["base_url"]

    model_name = os.environ.get("LLM_MODEL", config["default_model"])
    # OpenRouter free-tier and local Ollama models can take 90–120s+ to first
    # token. Anthropic/OpenAI direct typically return faster.
    timeout = 180.0 if provider in {"openrouter", "ollama"} else 60.0
    logger.debug(
        "LLM provider: %s | model: %s | base_url: %s | timeout: %.1fs",
        provider, model_name, base_url, timeout,
    )
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=1,
    ), model_name


def _is_openrouter_developer_instruction_error(exc: Exception) -> bool:
    """
    Return True when OpenRouter routes to a model without system-role support.

    Args:
        exc: Exception raised by the OpenAI-compatible client call.

    Returns:
        bool: True if the error text indicates developer/system instructions are
            unsupported on the routed model.
    """
    message = str(exc).lower()
    return (
        "developer instruction is not enabled" in message
        or "system instruction is not enabled" in message
    )


def _is_openrouter_rate_limit_error(exc: Exception) -> bool:
    """
    Return True for common OpenRouter free-tier rate-limit responses.

    Args:
        exc: Exception raised by the OpenAI-compatible client call.

    Returns:
        bool: True if the error text indicates HTTP 429 / rate limiting.
    """
    message = str(exc).lower()
    return "429" in message or "rate limit" in message or "rate-limited" in message


def call_chat_with_fallback(
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    provider: str,
    agent_name: str,
    document_id: str,
) -> str:
    """
    Execute one chat completion with OpenRouter-specific resilience.

    Args:
        client: OpenAI-compatible client from get_llm_client() or agent client.
        model_name: Model name string (for OpenRouter this may be openrouter/free).
        system_prompt: System prompt text for the agent.
        user_message: User message text for the agent.
        max_tokens: Max completion tokens for the request.
        provider: LLM provider identifier from LLM_PROVIDER.
        agent_name: Human-readable agent label for logs.
        document_id: Source document identifier for logs.

    Returns:
        str: Non-empty assistant response text, stripped.

    Raises:
        ValueError: If the provider returns empty content.
        Exception: Re-raises provider exceptions after fallback/retry exhaustion.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    max_attempts = 3 if provider == "openrouter" else 1
    downgraded_system_role = False

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                max_tokens=max_tokens,
                messages=messages,
            )
            # Guard against empty `choices` arrays (rare but seen on some
            # OpenRouter free-tier responses where the upstream model rejects
            # the call without raising an HTTP error).  Without this we
            # IndexError outside the try block in callers.
            if not response.choices:
                if provider == "openrouter" and attempt < max_attempts:
                    logger.warning(
                        "%s empty choices array (attempt %d/%d) for '%s' — retrying",
                        agent_name, attempt, max_attempts, document_id,
                    )
                    time.sleep(float(attempt * 2))
                    continue
                raise ValueError(
                    f"{agent_name}: empty choices for '{document_id}' "
                    f"(provider={provider}, model={model_name})"
                )
            content = response.choices[0].message.content
            if not content:
                # OpenRouter free routing sometimes returns empty content when
                # the routed model refuses or times out internally. Treat this
                # as retryable so the next attempt may land on a different model.
                if provider == "openrouter" and attempt < max_attempts:
                    logger.warning(
                        "%s empty completion (attempt %d/%d) for '%s' — retrying",
                        agent_name,
                        attempt,
                        max_attempts,
                        document_id,
                    )
                    time.sleep(float(attempt * 2))
                    continue
                raise ValueError(
                    f"{agent_name}: empty completion for '{document_id}' "
                    f"(provider={provider}, model={model_name})"
                )
            return content.strip()
        except Exception as exc:
            if (
                provider == "openrouter"
                and not downgraded_system_role
                and _is_openrouter_developer_instruction_error(exc)
            ):
                logger.warning(
                    "%s OpenRouter role fallback for '%s': %s",
                    agent_name,
                    document_id,
                    exc,
                )
                merged_prompt = (
                    "SYSTEM INSTRUCTIONS:\n"
                    f"{system_prompt}\n\n"
                    "USER REQUEST:\n"
                    f"{user_message}"
                )
                messages = [{"role": "user", "content": merged_prompt}]
                downgraded_system_role = True
                continue

            if (
                provider == "openrouter"
                and attempt < max_attempts
                and _is_openrouter_rate_limit_error(exc)
            ):
                backoff_seconds = float(attempt * 3)
                logger.warning(
                    "%s OpenRouter rate-limit retry %d/%d for '%s' after %.1fs: %s",
                    agent_name,
                    attempt,
                    max_attempts,
                    document_id,
                    backoff_seconds,
                    exc,
                )
                time.sleep(backoff_seconds)
                continue
            raise
