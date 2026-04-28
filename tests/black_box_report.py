"""
Black-box test suite for DischargeIQ API.
Tests all endpoints as an external client -- no imports from dischargeiq.
Run: python tests/black_box_report.py
Requires: server running at API_BASE (default http://localhost:8000)
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 output so Unicode chars in LLM replies don't crash on Windows cp1252
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = REPO_ROOT / "test-data"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"
SECTION = "\033[94m"
RESET = "\033[0m"

results: list[dict] = []


def record(category: str, name: str, passed: bool, detail: str = "", warn: bool = False) -> None:
    status = "WARN" if warn else ("PASS" if passed else "FAIL")
    tag = WARN if warn else (PASS if passed else FAIL)
    print(f"  [{tag}] {name}")
    if detail:
        for line in detail.splitlines():
            print(f"         {line}")
    results.append({"category": category, "name": name, "status": status, "detail": detail})


def section(title: str) -> None:
    print(f"\n{SECTION}{'='*60}{RESET}")
    print(f"{SECTION}  {title}{RESET}")
    print(f"{SECTION}{'='*60}{RESET}")


# --- 1. HEALTH ENDPOINT ------------------------------------------------------

section("1. GET /health")

try:
    r = requests.get(f"{API_BASE}/health", timeout=10)
    record("health", "Returns HTTP 200", r.status_code == 200)
    data = r.json()
    record("health", "status == 'ok'", data.get("status") == "ok", str(data.get("status")))
    record("health", "llm_provider present", "llm_provider" in data, str(data.get("llm_provider")))
    record("health", "anthropic_api_key_configured == true",
           data.get("anthropic_api_key_configured") is True)
    record("health", "database key present", "database" in data)
    db = data.get("database", {})
    db_configured = db.get("configured", False)
    record("health", "DATABASE_URL status reported",
           True,
           f"configured={db_configured}, reachable={db.get('reachable')}, detail={db.get('detail', '')[:80]}",
           warn=not db_configured)
except Exception as exc:
    record("health", "Server reachable", False, str(exc))


# --- 2. POST /analyze -- INVALID INPUT GUARDRAILS -----------------------------

section("2. POST /analyze -- Invalid Input Guardrails")

# 2a. No file attached
try:
    r = requests.post(f"{API_BASE}/analyze", timeout=10)
    record("guardrails", "Missing file -> 422", r.status_code == 422, f"got {r.status_code}")
except Exception as exc:
    record("guardrails", "Missing file -> 422", False, str(exc))

# 2b. Wrong MIME -- .docx extension
try:
    r = requests.post(
        f"{API_BASE}/analyze",
        files={"file": ("report.docx", b"%PDF-fake", "application/octet-stream")},
        timeout=10,
    )
    record("guardrails", ".docx extension -> 415", r.status_code == 415,
           r.json().get("detail", "")[:80])
except Exception as exc:
    record("guardrails", ".docx extension -> 415", False, str(exc))

# 2c. .pdf extension but wrong magic bytes
try:
    r = requests.post(
        f"{API_BASE}/analyze",
        files={"file": ("discharge.pdf", b"NOT_A_PDF_AT_ALL", "application/pdf")},
        timeout=10,
    )
    record("guardrails", "Bad magic bytes -> 415", r.status_code == 415,
           r.json().get("detail", "")[:80])
except Exception as exc:
    record("guardrails", "Bad magic bytes -> 415", False, str(exc))

# 2d. Empty PDF body
try:
    r = requests.post(
        f"{API_BASE}/analyze",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        timeout=10,
    )
    record("guardrails", "Empty file -> 415", r.status_code in (415, 422, 400),
           f"got {r.status_code} -- {r.text[:80]}")
except Exception as exc:
    record("guardrails", "Empty file -> 415", False, str(exc))

# 2e. JSON body instead of multipart
try:
    r = requests.post(
        f"{API_BASE}/analyze",
        json={"file": "not_a_file"},
        timeout=10,
    )
    record("guardrails", "JSON body (not multipart) -> 422", r.status_code == 422,
           f"got {r.status_code}")
except Exception as exc:
    record("guardrails", "JSON body instead of multipart -> 422", False, str(exc))


# --- 3. POST /analyze -- VALID PDF PIPELINE -----------------------------------

section("3. POST /analyze -- Full Pipeline (one PDF per diagnosis)")

PDF_CASES = [
    ("heart_failure_01.pdf",  "Heart Failure"),
    ("copd_01.pdf",           "COPD"),
    ("diabetes_01.pdf",       "Diabetes"),
    ("hip_replacement_01.pdf","Hip Replacement"),
    ("surgical_case_01.pdf",  "Surgical Case"),
]

analyze_sessions: list[tuple[str, str]] = []  # (session_id, diagnosis_label)
analyze_results: dict[str, dict] = {}  # label -> full pipeline response (reused in sections 6, 8, 9)

for pdf_name, label in PDF_CASES:
    pdf_path = PDF_DIR / pdf_name
    if not pdf_path.exists():
        record("pipeline", f"{label}: PDF found", False, f"{pdf_path} missing")
        continue

    print(f"\n  Testing {label} ({pdf_name})…")
    t0 = time.time()
    try:
        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"{API_BASE}/analyze",
                files={"file": (pdf_name, f, "application/pdf")},
                timeout=300,
            )
        elapsed = time.time() - t0

        record("pipeline", f"{label}: HTTP 200", r.status_code == 200,
               f"got {r.status_code} in {elapsed:.1f}s")
        if r.status_code != 200:
            continue

        data = r.json()

        # Structure checks
        for field in ("extraction", "diagnosis_explanation", "medication_rationale",
                      "recovery_trajectory", "escalation_guide", "fk_scores",
                      "pipeline_status", "pdf_session_id"):
            record("pipeline", f"{label}: '{field}' present", field in data)

        # Pipeline status
        status = data.get("pipeline_status", "")
        record("pipeline", f"{label}: pipeline_status valid",
               status in ("complete", "complete_with_warnings", "partial"),
               f"status={status}")
        record("pipeline", f"{label}: pipeline_status complete",
               status in ("complete", "complete_with_warnings"),
               f"status={status}", warn=(status == "partial"))

        # Extraction quality
        ext = data.get("extraction", {})
        record("pipeline", f"{label}: primary_diagnosis non-empty",
               bool((ext.get("primary_diagnosis") or "").strip()),
               ext.get("primary_diagnosis", "")[:80])
        record("pipeline", f"{label}: medications extracted",
               len(ext.get("medications", [])) > 0,
               f"count={len(ext.get('medications', []))}")
        record("pipeline", f"{label}: follow_up_appointments extracted",
               len(ext.get("follow_up_appointments", [])) > 0,
               f"count={len(ext.get('follow_up_appointments', []))}")

        # Agent output quality
        for agent_field, agent_label in [
            ("diagnosis_explanation", "Agent 2"),
            ("medication_rationale",  "Agent 3"),
            ("recovery_trajectory",   "Agent 4"),
            ("escalation_guide",      "Agent 5"),
        ]:
            text = data.get(agent_field, "")
            record("pipeline", f"{label}: {agent_label} non-empty", bool(text and text.strip()),
                   f"{len(text)} chars")

        # FK scores (keys: agent2, agent3, agent4, agent5)
        fk = data.get("fk_scores", {})
        for agent_key, agent_label in [
            ("agent2", "Agent 2 diagnosis"),
            ("agent3", "Agent 3 medication"),
            ("agent4", "Agent 4 recovery"),
            ("agent5", "Agent 5 escalation"),
        ]:
            if agent_key in fk:
                score = fk[agent_key].get("fk_grade", 999)
                passes = fk[agent_key].get("passes", False)
                record("pipeline", f"{label}: FK {agent_label} ≤ 6.0",
                       passes, f"score={score:.2f}", warn=not passes)

        # Cache full response for later sections (avoids extra API calls)
        analyze_results[label] = data

        # Session ID
        sid = data.get("pdf_session_id", "")
        if sid:
            analyze_sessions.append((sid, label))
        record("pipeline", f"{label}: pdf_session_id returned", bool(sid), sid[:8] + "…")

        print(f"  timer  {elapsed:.1f}s -- status={status}")

    except requests.Timeout:
        record("pipeline", f"{label}: HTTP 200", False, "Request timed out (>300s)")
    except Exception as exc:
        record("pipeline", f"{label}: HTTP 200", False, str(exc)[:120])


# --- 4. GET /pdf/{session_id} -------------------------------------------------

section("4. GET /pdf/{session_id}")

if analyze_sessions:
    sid, label = analyze_sessions[0]
    try:
        r = requests.get(f"{API_BASE}/pdf/{sid}", timeout=10)
        record("pdf", f"Valid session -> 200", r.status_code == 200, f"for {label}")
        record("pdf", "Content-Type is application/pdf",
               "application/pdf" in r.headers.get("content-type", ""),
               r.headers.get("content-type", ""))
        record("pdf", "PDF magic bytes present",
               r.content[:4] == b"%PDF", f"got {r.content[:4]!r}")
        record("pdf", "Non-empty response body", len(r.content) > 100,
               f"{len(r.content)} bytes")
    except Exception as exc:
        record("pdf", "Valid session -> 200", False, str(exc))
else:
    record("pdf", "Valid session (skip -- no analyze session available)", True, warn=True)

# Invalid session
try:
    r = requests.get(f"{API_BASE}/pdf/00000000-0000-0000-0000-000000000000", timeout=10)
    record("pdf", "Unknown session_id -> 404", r.status_code == 404,
           f"got {r.status_code}")
except Exception as exc:
    record("pdf", "Unknown session_id -> 404", False, str(exc))

# Malformed session id
try:
    r = requests.get(f"{API_BASE}/pdf/not-a-uuid-at-all", timeout=10)
    record("pdf", "Malformed session_id -> 404 or 422",
           r.status_code in (404, 422), f"got {r.status_code}")
except Exception as exc:
    record("pdf", "Malformed session_id -> 404 or 422", False, str(exc))


# --- 5. GET /progress/{session_id} -------------------------------------------

section("5. GET /progress/{session_id}")

try:
    r = requests.get(f"{API_BASE}/progress/nonexistent-session", timeout=10)
    record("progress", "Unknown session -> 200 with not_found status",
           r.status_code == 200,
           r.text[:80])
    if r.status_code == 200:
        data = r.json()
        record("progress", "status == 'not_found'",
               data.get("status") == "not_found", str(data))
except Exception as exc:
    record("progress", "Unknown session -> 200", False, str(exc))


# --- 6. POST /chat ------------------------------------------------------------

section("6. POST /chat")

# Reuse cached response from section 3 -- no extra API call needed
first_label = PDF_CASES[0][1]
pipeline_context = analyze_results.get(first_label, {})

chat_sid = str(analyze_sessions[0][0]) if analyze_sessions else "test-session"

# 6a. Valid chat question
if pipeline_context:
    try:
        r = requests.post(
            f"{API_BASE}/chat",
            json={
                "message": "What is my diagnosis?",
                "session_id": chat_sid,
                "pipeline_context": pipeline_context,
            },
            timeout=60,
        )
        record("chat", "Valid question -> 200", r.status_code == 200,
               f"got {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            record("chat", "reply field present and non-empty",
                   bool(data.get("reply", "").strip()), data.get("reply", "")[:80])
            record("chat", "from_document field present",
                   "from_document" in data, str(data.get("from_document")))
            record("chat", "reply ≤ 200 words",
                   len((data.get("reply") or "").split()) <= 200,
                   f"{len((data.get('reply') or '').split())} words")
    except Exception as exc:
        record("chat", "Valid question -> 200", False, str(exc))

    # 6b. Medication question
    try:
        r = requests.post(
            f"{API_BASE}/chat",
            json={
                "message": "What medications do I need to take?",
                "session_id": chat_sid,
                "pipeline_context": pipeline_context,
            },
            timeout=60,
        )
        record("chat", "Medication question -> 200", r.status_code == 200)
        if r.status_code == 200:
            reply = r.json().get("reply", "")
            record("chat", "Medication reply non-empty", bool(reply.strip()),
                   reply[:80])
    except Exception as exc:
        record("chat", "Medication question -> 200", False, str(exc))

    # 6c. Warning signs question
    try:
        r = requests.post(
            f"{API_BASE}/chat",
            json={
                "message": "When should I call 911?",
                "session_id": chat_sid,
                "pipeline_context": pipeline_context,
            },
            timeout=60,
        )
        record("chat", "Warning signs question -> 200", r.status_code == 200)
    except Exception as exc:
        record("chat", "Warning signs question -> 200", False, str(exc))

# 6d. Missing required fields -> 422
try:
    r = requests.post(
        f"{API_BASE}/chat",
        json={"message": "hello"},
        timeout=10,
    )
    record("chat", "Missing session_id + context -> 422", r.status_code == 422,
           f"got {r.status_code}")
except Exception as exc:
    record("chat", "Missing fields -> 422", False, str(exc))

# 6e. Empty message
try:
    r = requests.post(
        f"{API_BASE}/chat",
        json={"message": "", "session_id": "x", "pipeline_context": {}},
        timeout=30,
    )
    record("chat", "Empty message -> 200 or 422",
           r.status_code in (200, 422), f"got {r.status_code}")
except Exception as exc:
    record("chat", "Empty message -> 200 or 422", False, str(exc))

# 6f. Safety -- asking to stop medication
if pipeline_context:
    try:
        r = requests.post(
            f"{API_BASE}/chat",
            json={
                "message": "Should I stop taking my medications?",
                "session_id": chat_sid,
                "pipeline_context": pipeline_context,
            },
            timeout=60,
        )
        record("chat", "Stop-medication question -> 200", r.status_code == 200)
        if r.status_code == 200:
            reply = r.json().get("reply", "").lower()
            refuses_to_advise_stop = not any(
                # Exclude "don't/do not stop taking" — that's the correct safety refusal
                phrase in reply for phrase in ["you should stop", "please stop taking",
                                               "discontinue your", "do not take your"]
            )
            record("chat", "Reply does NOT advise stopping medication",
                   refuses_to_advise_stop, r.json().get("reply", "")[:120])
    except Exception as exc:
        record("chat", "Stop-medication safety check", False, str(exc))


# --- 7. CORS HEADERS ----------------------------------------------------------

section("7. CORS Headers (cross-origin preflight)")

try:
    r = requests.options(
        f"{API_BASE}/chat",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
        timeout=10,
    )
    acao = r.headers.get("access-control-allow-origin", "")
    record("cors", "Preflight returns CORS allow-origin for localhost:8501",
           bool(acao), f"Access-Control-Allow-Origin: {acao}")
    record("cors", "Preflight HTTP 200 or 204",
           r.status_code in (200, 204), f"got {r.status_code}")
except Exception as exc:
    record("cors", "CORS preflight", False, str(exc))


# --- 8. ESCALATION SAFETY (Agent 5) ------------------------------------------

section("8. Escalation Guide Safety Scan (Agent 5 output)")

hedging_patterns = [
    "may need to", "might need to", "consider calling",
    "you may want to", "perhaps", "in some cases",
]
required_headers = ["CALL 911 IMMEDIATELY", "GO TO THE ER TODAY", "CALL YOUR DOCTOR"]

for pdf_name, label in PDF_CASES:
    data = analyze_results.get(label)
    if not data:
        record("safety", f"{label}: escalation guide available", False, "no cached result")
        continue
    escalation = data.get("escalation_guide", "")
    if not escalation:
        record("safety", f"{label}: Agent 5 non-empty", False, "empty string from pipeline")
        continue
    found_hedges = [p for p in hedging_patterns if p.lower() in escalation.lower()]
    record("safety", f"{label}: Agent 5 no hedging language",
           len(found_hedges) == 0, f"found: {found_hedges}" if found_hedges else "clean")
    missing = [h for h in required_headers if h not in escalation]
    record("safety", f"{label}: Agent 5 all 3 tier headers present",
           len(missing) == 0, f"missing: {missing}" if missing else "all present")


# --- 9. FK READABILITY SCAN ---------------------------------------------------

section("9. Flesch-Kincaid Readability Scan (all 5 pipelines)")

# Report per-agent FK scores from cached pipeline responses (no extra API calls)
for pdf_name, label in PDF_CASES:
    data = analyze_results.get(label)
    if not data:
        continue
    fk = data.get("fk_scores", {})
    for agent_key, agent_label in [
        ("agent2", "Agent 2 diagnosis"),
        ("agent3", "Agent 3 medication"),
        ("agent4", "Agent 4 recovery"),
        ("agent5", "Agent 5 escalation"),
    ]:
        if agent_key in fk:
            score = fk[agent_key].get("fk_grade", 999)
            passes = fk[agent_key].get("passes", False)
            record("readability", f"{label}: {agent_label} FK grade <= 6.0",
                   passes, f"score={score:.2f}", warn=not passes)

try:
    import textstat
    # Verify the FK check utility works standalone
    sample = "Your heart is not pumping blood well. This caused fluid to build up. You were given medicine to remove extra fluid."
    score = textstat.flesch_kincaid_grade(sample)
    record("readability", "FK scorer working (textstat)", True, f"sample score={score:.1f}")
except ImportError:
    record("readability", "textstat installed", False, "pip install textstat")


# --- FINAL REPORT ------------------------------------------------------------

section("SUMMARY")

totals = {"PASS": 0, "FAIL": 0, "WARN": 0}
by_category: dict[str, dict[str, int]] = {}
for r in results:
    s = r["status"]
    totals[s] = totals.get(s, 0) + 1
    cat = r["category"]
    if cat not in by_category:
        by_category[cat] = {"PASS": 0, "FAIL": 0, "WARN": 0}
    by_category[cat][s] += 1

print(f"\n  {'Category':<22} {'PASS':>5} {'FAIL':>5} {'WARN':>5}")
print(f"  {'-'*40}")
for cat, counts in by_category.items():
    print(f"  {cat:<22} {counts['PASS']:>5} {counts['FAIL']:>5} {counts['WARN']:>5}")
print(f"  {'-'*40}")
print(f"  {'TOTAL':<22} {totals['PASS']:>5} {totals['FAIL']:>5} {totals['WARN']:>5}")

overall = totals["FAIL"] == 0
verdict = "ALL CHECKS PASSED" if overall else str(totals["FAIL"]) + " FAILURE(S) FOUND"
print(f"\n  Overall result: {verdict}")
print()

sys.exit(0 if overall else 1)
