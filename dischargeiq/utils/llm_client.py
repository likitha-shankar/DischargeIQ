"""
dischargeiq/utils/llm_client.py

Shared LLM provider factory used by all DischargeIQ agents.

Reads LLM_PROVIDER and LLM_MODEL from the environment and returns an
OpenAI-compatible client pointed at the chosen backend. Every agent imports
get_llm_client() from here instead of defining its own routing logic.

Supported providers (set LLM_PROVIDER in .env):
  openrouter (default) — https://openrouter.ai       needs OPENROUTER_API_KEY
  openai               — https://api.openai.com       needs OPENAI_API_KEY
  anthropic            — https://api.anthropic.com    needs ANTHROPIC_API_KEY
  ollama               — http://localhost:11434        no API key required

Override the default model for any provider with LLM_MODEL in .env.
Override the Ollama base URL with OLLAMA_BASE_URL (for remote/Docker installs).
"""

import logging
import os
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

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
        "default_model": "claude-sonnet-4-6",
    },
    "ollama": {
        # Ollama exposes an OpenAI-compatible endpoint locally.
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,  # "ollama" is used as a placeholder — no real key needed
        "default_model": "llama3.2",
    },
}


def get_llm_client() -> tuple[OpenAI, str]:
    """
    Build an OpenAI-compatible client and resolve the model name from env vars.

    Reads LLM_PROVIDER (default: openrouter) to select the backend, then
    reads the provider-specific API key and base URL. LLM_MODEL overrides the
    provider default model when set.

    Returns:
        tuple[OpenAI, str]: Configured client and the resolved model name string.

    Raises:
        ValueError: If LLM_PROVIDER is set to an unrecognised value.
        KeyError:   If the required API key env var for the chosen provider is
                    missing from the environment.
    """
    provider = os.environ.get("LLM_PROVIDER", "openrouter").lower()

    if provider not in _PROVIDER_DEFAULTS:
        supported = ", ".join(_PROVIDER_DEFAULTS)
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. "
            f"Supported values: {supported}"
        )

    config = _PROVIDER_DEFAULTS[provider]

    # Ollama does not require a real API key; pass a placeholder string so the
    # OpenAI client constructor does not reject a None value.
    if config["api_key_env"] is None:
        api_key = "ollama"
    else:
        api_key = os.environ[config["api_key_env"]]

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
            content = response.choices[0].message.content
            if not content:
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
