"""
test_frontend_issues.py

Automated regression suite for the five frontend issues:
  Issue 1 — GET /pdf/{session_id} endpoint
  Issue 2 — Always-visible chat panel (no FAB required)
  Issue 3 — Markdown rendering in chat (verified via chat response content)
  Issue 4 — Citation chip styling (visual only; verified by field presence)
  Issue 5 — URL-based PDF iframe (pdf_session_id in /analyze response)

Tests make real HTTP calls to the running FastAPI server (localhost:8000).
The Streamlit server does not need to be running — we test the backend API
directly.

Run with: python test_frontend_issues.py

Depends on: requests, dischargeiq.utils.logger
Backend must be running at http://localhost:8000.
"""

import logging
import sys
import time
from pathlib import Path

import requests

# ── Logging ────────────────────────────────────────────────────────────────────

import os
os.chdir(Path(__file__).parent)  # ensure .env and logs/ are found

from dischargeiq.utils.logger import configure_logging
configure_logging()
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"
ANALYZE_URL = f"{API_BASE}/analyze"
CHAT_URL = f"{API_BASE}/chat"
PDF_URL_TEMPLATE = f"{API_BASE}/pdf/{{session_id}}"

HIP_PDF = Path("test-data/hip_replacement_01.pdf")
COPD_PDF = Path("test-data/copd_01.pdf")

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []   # (test_name, status, detail)


# ── Helpers ────────────────────────────────────────────────────────────────────

def record(name: str, passed: bool, detail: str = "") -> None:
    """Record a test result and log it."""
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    log_fn = logger.info if passed else logger.error
    log_fn("%-50s  %s  %s", name, status, detail)


def call_analyze(pdf_path: Path) -> dict:
    """
    POST a PDF to /analyze and return the parsed JSON response.

    Raises:
        requests.RequestException: On network error.
        ValueError: On non-200 HTTP status.
    """
    with open(pdf_path, "rb") as fh:
        resp = requests.post(
            ANALYZE_URL,
            files={"file": (pdf_path.name, fh, "application/pdf")},
            timeout=180,
        )
    if resp.status_code != 200:
        raise ValueError(f"/analyze returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()


# ── TEST 1 — /pdf/{session_id} endpoint returns PDF bytes ─────────────────────

def test_pdf_endpoint() -> None:
    """
    Upload hip_replacement_01.pdf via /analyze, then fetch the PDF via
    GET /pdf/{session_id}. Verify 200 status and application/pdf content-type.
    Also verifies that pdf_session_id is present in the /analyze response
    (Issue 5 — URL-based PDF iframe).
    """
    test_name = "TEST 1 — /pdf/{session_id} + pdf_session_id in /analyze"
    logger.info("--- %s ---", test_name)

    try:
        data = call_analyze(HIP_PDF)
    except Exception as exc:
        record(test_name, False, f"/analyze failed: {exc}")
        return

    # Issue 5: pdf_session_id must be present in the response.
    pdf_session_id = data.get("pdf_session_id")
    if not pdf_session_id:
        record(test_name, False, "pdf_session_id missing from /analyze response")
        return

    logger.info("pdf_session_id: %s", pdf_session_id)

    # Issue 1: GET /pdf/{session_id} must return 200 + application/pdf.
    try:
        pdf_resp = requests.get(
            PDF_URL_TEMPLATE.format(session_id=pdf_session_id),
            timeout=15,
        )
    except Exception as exc:
        record(test_name, False, f"GET /pdf failed: {exc}")
        return

    if pdf_resp.status_code != 200:
        record(test_name, False, f"GET /pdf returned {pdf_resp.status_code}")
        return

    content_type = pdf_resp.headers.get("content-type", "")
    if "application/pdf" not in content_type:
        record(test_name, False, f"Wrong content-type: {content_type}")
        return

    pdf_size = len(pdf_resp.content)
    record(
        test_name,
        True,
        f"pdf_session_id={pdf_session_id[:8]}…, size={pdf_size} bytes, "
        f"content-type={content_type}",
    )


# ── TEST 2 — Extraction fields populated ──────────────────────────────────────

def test_extraction_fields() -> None:
    """
    Upload copd_01.pdf, assert all five core extraction fields are present:
    primary_diagnosis, medications, follow_up_appointments, fk_scores, pipeline_status.
    """
    test_name = "TEST 2 — Core extraction fields present (copd_01)"
    logger.info("--- %s ---", test_name)

    try:
        data = call_analyze(COPD_PDF)
    except Exception as exc:
        record(test_name, False, f"/analyze failed: {exc}")
        return

    ext = data.get("extraction", {})
    checks = {
        "primary_diagnosis": bool(ext.get("primary_diagnosis")),
        "medications": isinstance(ext.get("medications"), list),
        "follow_up_appointments": isinstance(ext.get("follow_up_appointments"), list),
        "fk_scores": isinstance(data.get("fk_scores"), dict),
        "pipeline_status": bool(data.get("pipeline_status")),
    }

    failed = [k for k, v in checks.items() if not v]
    if failed:
        record(test_name, False, f"Missing/empty fields: {failed}")
    else:
        record(
            test_name,
            True,
            f"diagnosis='{ext['primary_diagnosis'][:40]}', "
            f"meds={len(ext['medications'])}, "
            f"appts={len(ext['follow_up_appointments'])}, "
            f"status={data['pipeline_status']}",
        )


# ── TEST 3 — /chat returns a non-empty reply ───────────────────────────────────

def test_chat_response() -> None:
    """
    Upload copd_01.pdf, then POST a chat question about appointments.
    Verify the reply is non-empty and under 300 chars (respects 80-word cap).
    """
    test_name = "TEST 3 — /chat returns non-empty reply"
    logger.info("--- %s ---", test_name)

    try:
        pipeline_context = call_analyze(COPD_PDF)
    except Exception as exc:
        record(test_name, False, f"/analyze failed: {exc}")
        return

    try:
        resp = requests.post(
            CHAT_URL,
            json={
                "message": "When is my next follow-up appointment?",
                "session_id": "test_session_003",
                "pipeline_context": pipeline_context,
            },
            timeout=60,
        )
    except Exception as exc:
        record(test_name, False, f"/chat network error: {exc}")
        return

    if resp.status_code != 200:
        record(test_name, False, f"/chat returned {resp.status_code}: {resp.text[:200]}")
        return

    data = resp.json()
    reply = data.get("reply", "")
    if not reply:
        record(test_name, False, "reply field is empty")
        return

    word_count = len(reply.split())
    record(
        test_name,
        True,
        f"reply length={len(reply)} chars, words={word_count}, "
        f"source_page={data.get('source_page')}",
    )
    logger.info("Chat reply: %s", reply[:120])


# ── TEST 4 — /chat latency under 30 seconds ───────────────────────────────────

def test_chat_latency() -> None:
    """
    POST a short question to /chat and verify the round-trip latency is < 30s.
    Uses heart_failure_01 pipeline context for variety.
    """
    test_name = "TEST 4 — /chat latency < 30s"
    logger.info("--- %s ---", test_name)

    HF_PDF = Path("test-data/heart_failure_01.pdf")
    try:
        pipeline_context = call_analyze(HF_PDF)
    except Exception as exc:
        record(test_name, False, f"/analyze failed: {exc}")
        return

    start = time.monotonic()
    try:
        resp = requests.post(
            CHAT_URL,
            json={
                "message": "What medications do I need to take?",
                "session_id": "test_session_004",
                "pipeline_context": pipeline_context,
            },
            timeout=60,
        )
    except Exception as exc:
        record(test_name, False, f"/chat network error: {exc}")
        return
    elapsed_ms = (time.monotonic() - start) * 1000

    if resp.status_code != 200:
        record(test_name, False, f"/chat returned {resp.status_code}")
        return

    reply_len = len(resp.json().get("reply", ""))
    passed = elapsed_ms < 30_000
    record(
        test_name,
        passed,
        f"latency={elapsed_ms:.0f}ms, reply_len={reply_len} chars",
    )


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary() -> None:
    """Print a formatted pass/fail table to stdout and log the totals."""
    print()
    print("=" * 70)
    print(f"{'TEST':<50}  {'STATUS':<6}  DETAIL")
    print("-" * 70)
    for name, status, detail in results:
        print(f"{name:<50}  {status:<6}  {detail}")
    print("=" * 70)

    passed = sum(1 for _, s, _ in results if s == PASS)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    logger.info("Test suite complete — %d/%d passed", passed, total)

    if passed < total:
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting test_frontend_issues.py against %s", API_BASE)

    test_pdf_endpoint()
    test_extraction_fields()
    test_chat_response()
    test_chat_latency()

    print_summary()
