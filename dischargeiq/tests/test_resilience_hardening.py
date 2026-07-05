"""
File: dischargeiq/tests/test_resilience_hardening.py
Owner: Likitha Shankar
Description: Deterministic resilience tests — pdfplumber extraction shims for weird layouts,
  corrupt PDF errors, scan-quality warnings, and mocked OpenRouter paths for empty completions,
  developer-role fallback, rate-limit retries, and exhaustion behavior in llm_client.
Key functions/classes: test_* functions, _FakePage, _FakePdf shims
Edge cases handled:
  - Uses monkeypatched pdfplumber.open and fake OpenAI client responses; no network I/O.
Dependencies: pytest, dischargeiq.agents.extraction_agent, dischargeiq.utils.llm_client
Called by: pytest default run (not marked slow).
"""

from types import SimpleNamespace

import pytest

from dischargeiq.agents import extraction_agent
from dischargeiq.utils.llm_client import call_chat_with_fallback


class _FakePage:
    """Minimal pdfplumber page shim for deterministic extraction tests."""

    def __init__(
        self,
        primary_text: str,
        *,
        fallback_text: str | None = None,
        tables: list[list[list[str | None]]] | None = None,
        width: int = 612,
    ) -> None:
        self.primary_text = primary_text
        self.fallback_text = fallback_text if fallback_text is not None else primary_text
        self.tables = tables or []
        self.width = width

    def extract_text(self, x_tolerance: int | None = None, y_tolerance: int | None = None) -> str:
        if x_tolerance is None and y_tolerance is None:
            return self.primary_text
        return self.fallback_text

    def extract_tables(self) -> list[list[list[str | None]]]:
        return self.tables


class _FakePdf:
    """Context-manager shim for pdfplumber.open()."""

    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages

    def __enter__(self) -> "_FakePdf":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeCompletions:
    """Captures chat-completion payloads and delegates behavior per call."""

    def __init__(self, handler) -> None:
        self._handler = handler
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._handler(kwargs, len(self.calls))


class _FakeClient:
    """OpenAI-compatible client shape: client.chat.completions.create()."""

    def __init__(self, handler) -> None:
        self.completions = _FakeCompletions(handler)
        self.chat = SimpleNamespace(completions=self.completions)


def _resp(content: str) -> SimpleNamespace:
    """Build minimal chat completion response object."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_weird_pdf_layout_extracts_fallback_text_and_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multi-column/table-heavy pages are preserved in extracted text."""
    page = _FakePage(
        primary_text="a\nb\nc\nd",
        fallback_text="Discharge Medications section with clearer grouping",
        tables=[[["Drug", "Dose"], ["Furosemide", "40 mg"]]],
        width=612,
    )
    monkeypatch.setattr(
        extraction_agent.pdfplumber,
        "open",
        lambda _path: _FakePdf([page]),
    )

    text = extraction_agent.extract_text_from_pdf("weird_layout.pdf")

    assert "[PAGE 1]" in text
    assert "Discharge Medications section with clearer grouping" in text
    assert "Drug | Dose" in text
    assert "Furosemide | 40 mg" in text


def test_malformed_pdf_raises_runtime_error_with_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Corrupt PDF parsing errors are wrapped with path+type context."""

    def _raise_corrupt(_path: str):
        raise ValueError("No /Root object! - Is this really a PDF?")

    monkeypatch.setattr(extraction_agent.pdfplumber, "open", _raise_corrupt)

    with pytest.raises(RuntimeError) as exc:
        extraction_agent.extract_text_from_pdf("corrupt.pdf")
    message = str(exc.value)
    assert "corrupt.pdf" in message
    assert "ValueError" in message


def test_image_only_pdf_gets_scan_quality_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Image-only/OCR-poor pages trigger explicit scan quality warning."""
    pages = [_FakePage(""), _FakePage(""), _FakePage("")]
    monkeypatch.setattr(
        extraction_agent.pdfplumber,
        "open",
        lambda _path: _FakePdf(pages),
    )

    text = extraction_agent.extract_text_from_pdf("image_only.pdf")
    assert "scanned images with limited extractable text" in text.lower()


def test_openrouter_rate_limit_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 retries back off and eventually return content when provider recovers."""
    attempts = {"n": 0}

    def _handler(_payload: dict, _call_index: int):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise Exception("Error code: 429 - rate limit exceeded")
        return _resp("Recovered answer")

    client = _FakeClient(_handler)
    monkeypatch.setattr("dischargeiq.utils.llm_client.time.sleep", lambda _s: None)

    content = call_chat_with_fallback(
        client=client,
        model_name="openrouter/free",
        system_prompt="System",
        user_message="User",
        max_tokens=128,
        provider="openrouter",
        agent_name="Agent X",
        document_id="doc-1",
    )

    assert content == "Recovered answer"
    assert attempts["n"] == 3


def test_openrouter_developer_instruction_fallback_downgrades_role() -> None:
    """Models without system-role support fall back to merged user message."""
    calls_seen: list[dict] = []

    def _handler(payload: dict, _call_index: int):
        calls_seen.append(payload)
        if len(calls_seen) == 1:
            raise Exception("Developer instruction is not enabled for this model")
        return _resp("ok")

    client = _FakeClient(_handler)

    content = call_chat_with_fallback(
        client=client,
        model_name="openrouter/free",
        system_prompt="SYSTEM PROMPT",
        user_message="USER PROMPT",
        max_tokens=128,
        provider="openrouter",
        agent_name="Agent X",
        document_id="doc-2",
    )

    assert content == "ok"
    assert len(calls_seen) == 2
    assert calls_seen[0]["messages"][0]["role"] == "system"
    assert calls_seen[1]["messages"][0]["role"] == "user"
    assert "SYSTEM INSTRUCTIONS:" in calls_seen[1]["messages"][0]["content"]
    assert "USER REQUEST:" in calls_seen[1]["messages"][0]["content"]


def test_openrouter_rate_limit_exhaustion_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent 429 errors surface after max retry budget."""

    def _handler(_payload: dict, _call_index: int):
        raise Exception("HTTP 429 rate limit")

    client = _FakeClient(_handler)
    monkeypatch.setattr("dischargeiq.utils.llm_client.time.sleep", lambda _s: None)
    # Disable cross-provider failover — this test asserts primary exhaustion.
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "none")

    with pytest.raises(Exception, match="429"):
        call_chat_with_fallback(
            client=client,
            model_name="openrouter/free",
            system_prompt="System",
            user_message="User",
            max_tokens=128,
            provider="openrouter",
            agent_name="Agent X",
            document_id="doc-3",
        )
    assert len(client.completions.calls) == 3


# ── Cross-provider failover (Sprint 1, Task 1.4) ───────────────────────────────


def test_failover_to_fallback_provider_when_primary_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Primary provider failure triggers one attempt on the fallback provider."""

    def _primary_handler(_payload: dict, _call_index: int):
        raise Exception("gemini 503 service unavailable")

    fallback_client = _FakeClient(lambda _p, _i: _resp("fallback answer"))
    monkeypatch.setattr(
        "dischargeiq.utils.llm_client.get_fallback_client",
        lambda: (fallback_client, "claude-haiku-4-5-20251001", "anthropic"),
    )

    content = call_chat_with_fallback(
        client=_FakeClient(_primary_handler),
        model_name="gemini-2.5-flash-lite",
        system_prompt="System",
        user_message="User",
        max_tokens=128,
        provider="gemini",
        agent_name="Agent X",
        document_id="doc-fo-1",
    )
    assert content == "fallback answer"
    # Fallback must use its own provider's model, never the primary's.
    assert fallback_client.completions.calls[0]["model"] == "claude-haiku-4-5-20251001"


def test_failover_skipped_when_fallback_is_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    """No failover loop: anthropic primary does not fail over to anthropic."""

    def _handler(_payload: dict, _call_index: int):
        raise Exception("anthropic overloaded")

    fallback_client = _FakeClient(lambda _p, _i: _resp("should not be called"))
    monkeypatch.setattr(
        "dischargeiq.utils.llm_client.get_fallback_client",
        lambda: (fallback_client, "claude-haiku-4-5-20251001", "anthropic"),
    )

    with pytest.raises(Exception, match="overloaded"):
        call_chat_with_fallback(
            client=_FakeClient(_handler),
            model_name="claude-haiku-4-5-20251001",
            system_prompt="System",
            user_message="User",
            max_tokens=128,
            provider="anthropic",
            agent_name="Agent X",
            document_id="doc-fo-2",
        )
    assert fallback_client.completions.calls == []


def test_failover_reraises_primary_error_when_fallback_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both providers down: the primary exception is what surfaces to callers."""

    monkeypatch.setattr(
        "dischargeiq.utils.llm_client.get_fallback_client",
        lambda: (
            _FakeClient(lambda _p, _i: (_ for _ in ()).throw(Exception("claude also down"))),
            "claude-haiku-4-5-20251001",
            "anthropic",
        ),
    )

    with pytest.raises(Exception, match="gemini down"):
        call_chat_with_fallback(
            client=_FakeClient(lambda _p, _i: (_ for _ in ()).throw(Exception("gemini down"))),
            model_name="gemini-2.5-flash-lite",
            system_prompt="System",
            user_message="User",
            max_tokens=128,
            provider="gemini",
            agent_name="Agent X",
            document_id="doc-fo-3",
        )


def test_get_fallback_client_disabled_and_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_FALLBACK_PROVIDER=none or a missing API key disables failover."""
    from dischargeiq.utils import llm_client

    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "none")
    assert llm_client.get_fallback_client() is None

    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_client.get_fallback_client() is None


def test_get_fallback_client_builds_anthropic_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default fallback is anthropic with its dated default model."""
    from dischargeiq.utils import llm_client

    monkeypatch.delenv("LLM_FALLBACK_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    llm_client._client_cache.pop("fallback:anthropic", None)
    try:
        fb = llm_client.get_fallback_client()
        assert fb is not None
        _client, model, provider = fb
        assert provider == "anthropic"
        assert model == llm_client.DEFAULT_ANTHROPIC_MODEL
    finally:
        llm_client._client_cache.pop("fallback:anthropic", None)


# ── Vertex AI provider path (HIPAA/BAA readiness) ──────────────────────────────


def test_vertex_provider_requires_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PROVIDER=vertex without VERTEX_PROJECT raises a clear ValueError."""
    from dischargeiq.utils import llm_client

    monkeypatch.setenv("LLM_PROVIDER", "vertex")
    monkeypatch.delenv("VERTEX_PROJECT", raising=False)
    with pytest.raises(ValueError, match="VERTEX_PROJECT"):
        llm_client.get_llm_client()


def test_vertex_provider_builds_project_scoped_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vertex client points at the project-scoped OpenAI-compat endpoint with a token."""
    from types import SimpleNamespace as _NS

    from dischargeiq.utils import llm_client

    fake_creds = _NS(valid=True, token="fake-oauth-token")
    fake_google_auth = _NS(default=lambda scopes: (fake_creds, "proj"))
    monkeypatch.setitem(__import__("sys").modules, "google.auth", fake_google_auth)
    monkeypatch.setitem(
        __import__("sys").modules,
        "google.auth.transport.requests",
        _NS(Request=lambda: None),
    )
    monkeypatch.setattr(llm_client, "_vertex_creds", fake_creds)
    monkeypatch.setenv("LLM_PROVIDER", "vertex")
    monkeypatch.setenv("VERTEX_PROJECT", "dischargeiq-test")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    llm_client._client_cache.pop("vertex", None)
    try:
        client, model = llm_client.get_llm_client()
        assert model == "google/gemini-2.5-flash-lite"
        assert "dischargeiq-test" in str(client.base_url)
        assert "us-central1-aiplatform.googleapis.com" in str(client.base_url)
    finally:
        llm_client._client_cache.pop("vertex", None)
        monkeypatch.setattr(llm_client, "_vertex_creds", None)
