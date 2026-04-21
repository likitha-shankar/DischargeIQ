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
        "default_model": "claude-sonnet-4-20250514",
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
    logger.debug(
        "LLM provider: %s | model: %s | base_url: %s",
        provider, model_name, base_url,
    )
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=60.0,
        max_retries=1,
    ), model_name
