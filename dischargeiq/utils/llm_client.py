"""
File: dischargeiq/utils/llm_client.py
Owner: Likitha Shankar
Description: Central LLM routing - builds an OpenAI-compatible client for anthropic,
  openrouter, openai, ollama, or gemini from LLM_PROVIDER/LLM_MODEL and validates API keys with
  clear ValueError messages. call_chat_with_fallback adds OpenRouter retries for
  empty completions, developer-instruction role merge, and 429 backoff, plus one
  cross-provider failover attempt (LLM_FALLBACK_PROVIDER, default anthropic) when
  the primary provider fails after its retries.
Key functions/classes: require_provider_api_key, get_llm_client, get_fallback_client,
  call_chat_with_fallback
Edge cases handled:
  - OpenRouter empty content and rate limits retry with backoff; role fallback on
    unsupported developer-message errors; Ollama uses placeholder API key string.
Dependencies: openai (SDK); reads env vars only (no other dischargeiq imports).
Called by: dischargeiq.agents.extraction_agent, diagnosis_agent, patient_simulator_agent,
  dischargeiq.main (/chat), dischargeiq.tests.test_api_guardrails, test_resilience_hardening.
"""

import functools
import logging
import os
import time
from pathlib import Path

from openai import OpenAI

# Cache LLM clients by provider string - building OpenAI() constructs a
# connection pool internally. Under parallel asyncio.gather (4 agents per upload),
# four concurrent constructions are wasteful. The client is thread-safe and
# config is static at runtime, so caching per provider is safe.
_client_cache: dict[str, tuple] = {}

logger = logging.getLogger(__name__)

# Anthropic default: dated Haiku 4.5 (cheapest tier). Undated aliases can 404.
# For higher-quality eval / demos, set LLM_MODEL=claude-sonnet-4-20250514 in .env.
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# Default configuration per provider.
# Add a new provider here - no agent code needs to change.
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
    "gemini": {
        # Google Gemini exposes an OpenAI-compatible chat completions endpoint.
        # Auth uses GOOGLE_API_KEY. The system role is supported, so the shared
        # OpenAI SDK client works unchanged for Agents 1, 2, 6 and /chat. The
        # model name is read from LLM_MODEL - the default below is only a
        # fallback when LLM_MODEL is unset.
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GOOGLE_API_KEY",
        "default_model": "gemini-2.5-flash-lite",
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
        "api_key_env": None,  # "ollama" is used as a placeholder - no real key needed
        "default_model": "llama3.2",
    },
    "vertex": {
        # Google Vertex AI - same Gemini models as the "gemini" provider, but
        # served inside a GCP project where a HIPAA BAA can cover the calls.
        # This is the required provider before ANY real (non-synthetic) patient
        # document is processed. Auth uses short-lived OAuth tokens from
        # Application Default Credentials (gcloud auth application-default login
        # locally; the service account on Cloud Run), not a static API key.
        # base_url is built per-project in _get_vertex_client().
        "base_url": None,
        "api_key_env": None,
        "default_model": "google/gemini-2.5-flash-lite",  # Vertex needs google/ prefix
    },
}

# Vertex OAuth credentials - cached module-wide; tokens auto-refresh via
# google-auth when expired. Populated lazily on first vertex call.
_vertex_creds = None


def _get_vertex_client() -> tuple[OpenAI, str]:
    """
    Build (or refresh) the OpenAI-compatible client for Vertex AI.

    Vertex auth uses ~1h OAuth tokens, so unlike static-key providers the
    cached client must be rebuilt whenever the token has expired. google-auth
    handles refresh; this function re-creates the OpenAI client with the fresh
    token when needed.

    Returns:
        tuple[OpenAI, str]: Configured client and resolved model name.

    Raises:
        ValueError: If VERTEX_PROJECT is unset or google-auth is not installed.
    """
    global _vertex_creds

    project = os.environ.get("VERTEX_PROJECT", "").strip()
    if not project:
        raise ValueError(
            "LLM_PROVIDER=vertex requires VERTEX_PROJECT in .env "
            "(your GCP project ID). Optional: VERTEX_LOCATION (default us-central1). "
            "Authenticate with 'gcloud auth application-default login' locally, "
            "or a service account on Cloud Run."
        )
    location = os.environ.get("VERTEX_LOCATION", "us-central1").strip()

    try:
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise ValueError(
            "LLM_PROVIDER=vertex requires the google-auth package: "
            "pip install google-auth (listed in requirements.txt)."
        ) from exc

    if _vertex_creds is None:
        _vertex_creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    if not _vertex_creds.valid:
        _vertex_creds.refresh(Request())
        _client_cache.pop("vertex", None)  # token rotated - cached client is stale

    model_name = os.environ.get(
        "LLM_MODEL", _PROVIDER_DEFAULTS["vertex"]["default_model"]
    )
    if "vertex" in _client_cache:
        return _client_cache["vertex"]

    base_url = (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project}/locations/{location}/endpoints/openapi"
    )
    result = OpenAI(
        base_url=base_url,
        api_key=_vertex_creds.token,
        timeout=60.0,
        max_retries=1,
    ), model_name
    _client_cache["vertex"] = result
    return result


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
            f"For Gemini on all agents use LLM_PROVIDER=gemini and GOOGLE_API_KEY. "
            f"For Claude use LLM_PROVIDER=anthropic and LLM_MODEL={DEFAULT_ANTHROPIC_MODEL!r}."
        )


def get_llm_client() -> tuple[OpenAI, str]:
    """
    Build an OpenAI-compatible client and resolve the model name from env vars.

    Reads LLM_PROVIDER (default: gemini) to select the backend, then
    reads the provider-specific API key and base URL. LLM_MODEL overrides the
    provider default model when set.

    Returns:
        tuple[OpenAI, str]: Configured client and the resolved model name string.

    Raises:
        ValueError: If LLM_PROVIDER is invalid or the required API key is missing.
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()

    if provider not in _PROVIDER_DEFAULTS:
        supported = ", ".join(_PROVIDER_DEFAULTS)
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. "
            f"Supported values: {supported}"
        )

    # Vertex uses OAuth tokens with expiry - handled by its own builder.
    if provider == "vertex":
        return _get_vertex_client()

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

    if provider in _client_cache:
        return _client_cache[provider]

    # OpenRouter free-tier and local Ollama models can take 90–120s+ to first
    # token. Anthropic/OpenAI/Gemini direct typically return faster, so they
    # fall into the 60s timeout below (gemini is intentionally not in the
    # slow-provider set).
    timeout = 180.0 if provider in {"openrouter", "ollama"} else 60.0
    logger.debug(
        "LLM provider: %s | model: %s | base_url: %s | timeout: %.1fs",
        provider, model_name, base_url, timeout,
    )
    result = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=1,
    ), model_name
    _client_cache[provider] = result
    return result


@functools.lru_cache(maxsize=None)
def load_agent_prompt(prompt_filename: str) -> str:
    """
    Load a system prompt from dischargeiq/prompts/<prompt_filename>.

    Result is cached indefinitely - prompt files are static assets that do not
    change while the server is running. First call reads from disk; subsequent
    calls (across all agents and uploads) return the cached string with zero I/O.

    Replaces the per-agent _load_system_prompt() copies that were identical
    across agents 3–5 (and agents 1–2 had similar inline logic).

    Args:
        prompt_filename: Filename of the prompt, e.g. "agent3_system_prompt.txt".

    Returns:
        str: Full prompt text, whitespace-stripped.

    Raises:
        FileNotFoundError: If the file does not exist at the expected path.
    """
    path = Path(__file__).parent.parent / "prompts" / prompt_filename
    if not path.exists():
        raise FileNotFoundError(
            f"Agent prompt not found: {path}. "
            "Ensure the file exists under dischargeiq/prompts/."
        )
    return path.read_text(encoding="utf-8").strip()


def get_native_agent_client(provider: str) -> tuple:
    """
    Return (client, model_name) for agents that need native Anthropic SDK on the
    anthropic path and the shared OpenAI-compat client for all other providers.

    Agents 3–5 call messages.create() on the anthropic path (native SDK required)
    and chat.completions.create() on all other paths (OpenAI-compat client from
    get_llm_client()). This single function replaces the three identical _get_client()
    copies that previously lived in medication_agent, recovery_agent, and
    escalation_agent. Timeout (60s) and max_retries (1) match the values those
    copies had for the anthropic branch - confirmed identical before consolidation.

    Args:
        provider: Lowercase LLM_PROVIDER value (e.g. "gemini", "anthropic").

    Returns:
        tuple: (client, model_name). Client type depends on provider:
               anthropic → anthropic.Anthropic; all others → openai.OpenAI.

    Raises:
        ValueError: If provider is unsupported or its API key is missing.
        ImportError: If provider is "anthropic" but the anthropic package is absent.
    """
    if provider == "anthropic":
        import anthropic as _anthropic  # lazy import - not needed on Gemini path
        require_provider_api_key("anthropic")
        model = os.environ.get("LLM_MODEL", DEFAULT_ANTHROPIC_MODEL)
        client = _anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"].strip(),
            timeout=60.0,
            max_retries=1,
        )
        return client, model
    return get_llm_client()


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


def get_fallback_client() -> tuple[OpenAI, str, str] | None:
    """
    Build the cross-provider fallback client, if one is configured.

    Reads LLM_FALLBACK_PROVIDER (default: "anthropic"; "none" disables). The
    fallback fires only when its API key is present, so a missing key silently
    disables cross-provider failover rather than breaking the primary path.

    Returns:
        tuple[OpenAI, str, str] | None: (client, model_name, provider_name),
            or None when fallback is disabled or unconfigured.
    """
    fallback = os.environ.get("LLM_FALLBACK_PROVIDER", "anthropic").lower()
    if fallback in ("none", "") or fallback not in _PROVIDER_DEFAULTS:
        return None
    if fallback == "vertex":
        # Vertex uses OAuth tokens, not a static key; unconfigured → disabled.
        try:
            client, model = _get_vertex_client()
        except ValueError:
            return None
        return client, model, "vertex"
    config = _PROVIDER_DEFAULTS[fallback]
    key_env = config["api_key_env"]
    api_key = (os.environ.get(key_env, "") if key_env else "ollama").strip()
    if not api_key:
        return None

    cache_key = f"fallback:{fallback}"
    if cache_key in _client_cache:
        client, model = _client_cache[cache_key]
        return client, model, fallback

    # LLM_MODEL belongs to the primary provider - the fallback uses its own
    # provider default so a Gemini model name is never sent to Anthropic.
    # LLM_FALLBACK_MODEL overrides that default (e.g. an OpenRouter :free
    # model for zero-cost demo capacity when the primary quota is exhausted).
    model = os.environ.get("LLM_FALLBACK_MODEL", "").strip() or config["default_model"]
    client = OpenAI(
        base_url=config["base_url"],
        api_key=api_key,
        timeout=60.0,
        max_retries=1,
    )
    _client_cache[cache_key] = (client, model)
    return client, model, fallback


def read_anthropic_completion(response, agent_name: str, document_id: str) -> str:
    """
    Extract text from a native anthropic.Anthropic response with the same
    truncation guard the OpenAI-compat path has: a completion cut off by the
    token budget (stop_reason == "max_tokens") is unusable patient-facing
    text and must raise rather than ship a half-sentence.

    Args:
        response:    anthropic.types.Message from client.messages.create().
        agent_name:  Human-readable agent label for the error message.
        document_id: Source document identifier for the error message.

    Returns:
        str: Stripped completion text; "" when content is empty (callers
             already treat empty as a failure).

    Raises:
        ValueError: When the completion was truncated by max_tokens.
    """
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise ValueError(
            f"{agent_name}: completion truncated by max_tokens for "
            f"'{document_id}' (provider=anthropic-native)"
        )
    return response.content[0].text.strip() if response.content else ""


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
    Execute one chat completion with per-provider retries and cross-provider failover.

    Primary call runs on the given client with OpenRouter-specific resilience
    (empty-completion retries, role merge, 429 backoff). If the primary provider
    fails after its retries, one attempt is made on the fallback provider from
    get_fallback_client() (default: Anthropic, when ANTHROPIC_API_KEY is set).
    The original exception is re-raised if the fallback also fails or is not
    configured.

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
        Exception: Re-raises primary provider exceptions after fallback/retry exhaustion.
    """
    try:
        return _call_chat_once(
            client, model_name, system_prompt, user_message,
            max_tokens, provider, agent_name, document_id,
        )
    except Exception as primary_exc:
        fb = get_fallback_client()
        if fb is None or fb[2] == provider:
            raise
        fb_client, fb_model, fb_provider = fb
        logger.warning(
            "%s primary provider '%s' failed for '%s' - failing over to '%s' (%s): %s",
            agent_name, provider, document_id, fb_provider, fb_model, primary_exc,
        )
        try:
            return _call_chat_once(
                fb_client, fb_model, system_prompt, user_message,
                max_tokens, fb_provider, agent_name, document_id,
            )
        except Exception as fallback_exc:
            logger.error(
                "%s fallback provider '%s' also failed for '%s': %s",
                agent_name, fb_provider, document_id, fallback_exc,
            )
            raise primary_exc from fallback_exc


def _call_chat_once(
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
    Run one chat completion on a single provider with that provider's retries.

    This is the pre-failover body of call_chat_with_fallback: OpenRouter gets
    3 attempts with empty-completion retries, role-merge fallback, and 429
    backoff; every other provider gets a single attempt.

    Args/Returns/Raises: same contract as call_chat_with_fallback, minus the
    cross-provider failover.
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
                        "%s empty choices array (attempt %d/%d) for '%s' - retrying",
                        agent_name, attempt, max_attempts, document_id,
                    )
                    time.sleep(float(attempt * 2))
                    continue
                raise ValueError(
                    f"{agent_name}: empty choices for '{document_id}' "
                    f"(provider={provider}, model={model_name})"
                )
            # A completion cut off by the token budget is unusable for
            # patient-facing text (observed live July 2026: gemini-2.5-flash
            # spends its budget on thinking tokens, truncating every section
            # mid-sentence). Raising here lets call_chat_with_fallback route
            # the request to the fallback provider instead of shipping a
            # half-sentence to a patient.
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            if finish_reason == "length":
                raise ValueError(
                    f"{agent_name}: completion truncated by max_tokens for "
                    f"'{document_id}' (provider={provider}, model={model_name})"
                )
            content = response.choices[0].message.content
            if not content:
                # OpenRouter free routing sometimes returns empty content when
                # the routed model refuses or times out internally. Treat this
                # as retryable so the next attempt may land on a different model.
                if provider == "openrouter" and attempt < max_attempts:
                    logger.warning(
                        "%s empty completion (attempt %d/%d) for '%s' - retrying",
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
