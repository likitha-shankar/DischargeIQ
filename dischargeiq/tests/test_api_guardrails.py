"""
File: dischargeiq/tests/test_api_guardrails.py
Owner: Likitha Shankar
Description: Fast pytest suite (no live LLM) for upload validation helpers, provider key
  error shaping, and extraction completeness classification used by the API guardrails.
Key functions/classes: test_* module-level functions
Edge cases handled:
  - Asserts ValueError (not KeyError) on missing keys; HTTPException statuses for bad PDFs.
Dependencies: pytest, fastapi, dischargeiq.main, dischargeiq.models.extraction,
  dischargeiq.utils.llm_client, dischargeiq.utils.warnings
Called by: pytest (default non-slow run).
"""

import pytest

from fastapi import HTTPException

from dischargeiq.api.routes.analyze import validate_uploaded_pdf as _validate_uploaded_pdf
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.utils.llm_client import require_provider_api_key
from dischargeiq.utils.warnings import assess_extraction_completeness


def test_require_provider_api_key_raises_valueerror_not_keyerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing API key should surface a clear ValueError for operators."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        require_provider_api_key("anthropic")


def test_analyze_rejects_non_pdf_extension() -> None:
    """Validation helper raises 415 for non-PDF filenames."""
    with pytest.raises(HTTPException) as exc:
        _validate_uploaded_pdf("notes.docx", b"%PDF-pretend")
    assert exc.value.status_code == 415
    assert "Only PDF files are accepted" in str(exc.value.detail)


def test_analyze_rejects_bad_pdf_magic_bytes() -> None:
    """Validation helper raises 415 for renamed non-PDF content."""
    with pytest.raises(HTTPException) as exc:
        _validate_uploaded_pdf("looks_like_pdf.pdf", b"NOT_A_PDF")
    assert exc.value.status_code == 415
    assert "magic bytes missing" in str(exc.value.detail)


def test_analyze_rejects_oversized_pdf(monkeypatch) -> None:
    """Validation helper raises 413 when payload exceeds size cap."""
    monkeypatch.setattr("dischargeiq.api.routes.analyze._MAX_FILE_SIZE_BYTES", 10)
    with pytest.raises(HTTPException) as exc:
        _validate_uploaded_pdf("big.pdf", b"%PDF-1234567890")
    assert exc.value.status_code == 413
    assert "File exceeds" in str(exc.value.detail)


def test_completeness_flags_likely_non_discharge_summary() -> None:
    """Critical extraction gaps include explicit non-discharge warning."""
    extraction = ExtractionOutput(
        primary_diagnosis="",
        medications=[],
        red_flag_symptoms=[],
        extraction_warnings=[],
    )
    result = assess_extraction_completeness(extraction)
    assert result["is_critical"] is True
    assert any(
        "may not be a hospital discharge summary" in warning.lower()
        for warning in result["critical_warnings"]
    )


# ── Spend-gate: API key auth on LLM-cost routes ───────────────────────────────
# verify_api_key is a no-op when DISCHARGEIQ_API_KEY is unset, which is correct
# for local dev and was silently true in production - anyone with the URL could
# run the full pipeline on our bill. These pin the gate shut once the key is set.


def _keyed_client(monkeypatch: pytest.MonkeyPatch):
    """Build a TestClient for an app configured with an API key."""
    from fastapi.testclient import TestClient

    from dischargeiq.api.app import create_app

    monkeypatch.setenv("DISCHARGEIQ_API_KEY", "unit-test-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return TestClient(create_app())


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("post", "/analyze", {"files": {"file": ("a.pdf", b"%PDF-x", "application/pdf")}}),
        ("post", "/analyze/text", {"json": {"text": "x" * 400}}),
        ("post", "/quiz/generate", {"json": {"session_id": "s", "extraction": {}}}),
        ("post", "/quiz/score", {"json": {}}),
    ],
)
def test_llm_cost_routes_require_bearer_key(
    monkeypatch: pytest.MonkeyPatch, method: str, path: str, kwargs: dict
) -> None:
    """Every pipeline/quiz route rejects unauthenticated callers with 401."""
    client = _keyed_client(monkeypatch)
    assert getattr(client, method)(path, **kwargs).status_code == 401
    wrong = getattr(client, method)(
        path, headers={"Authorization": "Bearer wrong-key"}, **kwargs
    )
    assert wrong.status_code == 401


def test_correct_key_passes_auth_and_reaches_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid key gets past auth - 415 here is the route's own validation."""
    client = _keyed_client(monkeypatch)
    resp = client.post(
        "/analyze",
        files={"file": ("a.txt", b"not a pdf", "text/plain")},
        headers={"Authorization": "Bearer unit-test-key"},
    )
    assert resp.status_code == 415


def test_chat_stays_reachable_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    /chat is deliberately ungated: the Streamlit panel calls it from browser
    JavaScript, where a key would be readable in page source. 409 (no session
    context) proves the request reached the handler rather than being blocked.
    """
    client = _keyed_client(monkeypatch)
    resp = client.post("/chat", json={"message": "hi", "session_id": "nope"})
    assert resp.status_code == 409


def test_chat_refuses_caller_supplied_context_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reachable is not the same as free to abuse.

    Black-box testing on 15 Aug 2026 got a full grounded answer from two
    hand-written fields and no API key, which made /chat an open LLM endpoint
    for anyone holding the URL. Grounding context invented by an anonymous
    caller is now refused; only a session this server analysed (and /analyze
    IS gated) will be answered.
    """
    client = _keyed_client(monkeypatch)
    resp = client.post(
        "/chat",
        json={
            "message": "what are my medicines",
            "session_id": "invented-by-a-stranger",
            "pipeline_context": {
                "extraction": {"primary_diagnosis": "Heart failure"},
                "diagnosis_explanation": "Made up.",
            },
        },
    )
    assert resp.status_code == 401


def test_chat_accepts_caller_supplied_context_with_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The mobile app re-sends its own context when a session has been evicted,
    and it always carries the key. That path must keep working, or chat breaks
    on the phone every time the server restarts.
    """
    client = _keyed_client(monkeypatch)
    resp = client.post(
        "/chat",
        json={
            "message": "what are my medicines",
            "session_id": "evicted-session",
            "pipeline_context": {
                "extraction": {"primary_diagnosis": "Heart failure"},
                "diagnosis_explanation": "Your heart is not pumping well.",
            },
        },
        headers={"Authorization": "Bearer unit-test-key"},
    )
    # Not 401: the caller is authenticated, so the request reaches the service
    # (which then needs an LLM, unavailable in the suite - anything but 401
    # proves the gate let it through).
    assert resp.status_code != 401


def test_docs_hidden_when_keyed_and_shown_when_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """Interactive docs publish the endpoint map - off on keyed deployments."""
    from fastapi.testclient import TestClient

    from dischargeiq.api.app import create_app

    monkeypatch.delenv("API_DOCS_ENABLED", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    keyed = _keyed_client(monkeypatch)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert keyed.get(path).status_code == 404

    monkeypatch.delenv("DISCHARGEIQ_API_KEY", raising=False)
    assert TestClient(create_app()).get("/docs").status_code == 200


# ── Claude 5 thinking budget ──────────────────────────────────────────────────
# Claude 5 models run adaptive thinking when a request omits `thinking`, and
# max_tokens caps thinking plus the answer. Agent 1 asks for JSON at 4096, so
# on claude-sonnet-5 the thinking consumed the budget and the extraction came
# back truncated - a live "partial" pipeline the moment the fallback model was
# switched from Haiku 4.5 to Sonnet 5.


@pytest.mark.parametrize(
    "model",
    ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001"],
)
def test_thinking_disabled_for_claude_models(model: str) -> None:
    """Bounded-output agents must not spend max_tokens on thinking."""
    from dischargeiq.utils.llm_client import anthropic_extra_body

    assert anthropic_extra_body(model) == {"thinking": {"type": "disabled"}}


@pytest.mark.parametrize("model", ["claude-fable-5", "claude-mythos-5"])
def test_thinking_not_configured_for_always_thinking_models(model: str) -> None:
    """Fable/Mythos think unconditionally and 400 on an explicit disable."""
    from dischargeiq.utils.llm_client import anthropic_extra_body

    assert anthropic_extra_body(model) == {}


# ── Audience passthrough on every analyze path ────────────────────────────────
# The mobile app files a document under a person and derives the reader from
# that profile. Only POST /analyze forwarded it; the two scan paths dropped it,
# so a document photographed for a 6-year-old was written to the child instead
# of the caregiver. These pin the parameter to every entry point.


def _audience_capture(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stub _execute_pipeline and record the audience it was handed."""
    seen: dict = {}

    async def _fake_execute(**kwargs):
        seen.update(kwargs)
        return {"pipeline_status": "complete"}

    monkeypatch.setattr(
        "dischargeiq.api.routes.analyze._execute_pipeline", _fake_execute
    )
    return seen


def test_analyze_text_forwards_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from dischargeiq.main import create_app

    monkeypatch.delenv("DISCHARGEIQ_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    seen = _audience_capture(monkeypatch)

    response = TestClient(create_app()).post(
        "/analyze/text", json={"text": "x" * 400, "audience": "caregiver"}
    )
    assert response.status_code == 200
    assert seen["audience"] == "caregiver"


def test_analyze_text_audience_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    """Omitting it must stay valid - the backend then infers from the text."""
    from fastapi.testclient import TestClient

    from dischargeiq.main import create_app

    monkeypatch.delenv("DISCHARGEIQ_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    seen = _audience_capture(monkeypatch)

    response = TestClient(create_app()).post("/analyze/text", json={"text": "x" * 400})
    assert response.status_code == 200
    assert seen["audience"] is None


def test_analyze_image_forwards_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from dischargeiq.main import create_app

    monkeypatch.delenv("DISCHARGEIQ_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    seen = _audience_capture(monkeypatch)
    # Vision transcription is the only other network hop on this route.
    monkeypatch.setattr(
        "dischargeiq.api.routes.analyze.transcribe_document_images",
        lambda images: "y" * 400,
    )

    response = TestClient(create_app()).post(
        "/analyze/image",
        files={"files": ("page.jpg", b"\xff\xd8\xff-fake", "image/jpeg")},
        data={"audience": "caregiver"},
    )
    assert response.status_code == 200
    assert seen["audience"] == "caregiver"
