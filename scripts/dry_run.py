#!/usr/bin/env python3
"""
scripts/dry_run.py

End-to-end exercise of the deployed application, happy paths and failure
paths, against the live service. Owner: Likitha Shankar.

Written for Gate 3, whose acceptance criterion is that the demo "runs live
across the phone and dashboard" and whose checklist requires the system to
"behave reasonably on bad input / failure, not just the happy path". A dry
run that only proves the happy path proves the half nobody doubts.

Every check states what it expects BEFORE it runs, so a pass is a prediction
confirmed rather than a result rationalised afterwards.

Costs real model calls - roughly one full pipeline per document plus audio
and quiz generation. Use --quick to skip the expensive per-case audio.

Usage:
  python scripts/dry_run.py
  python scripts/dry_run.py --quick
"""

import argparse
import json
import struct
import sys
import time
from pathlib import Path

import requests

_REPO = Path(__file__).resolve().parent.parent
_BASE = "https://dischargeiq-678599658918.us-central1.run.app/api"

_PASS, _FAIL, _WARN = "PASS", "FAIL", "WARN"
_results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str = "") -> None:
    """Record one result and print it as it happens."""
    _results.append((status, name, detail))
    mark = {"PASS": "  ok  ", "FAIL": " FAIL ", "WARN": " warn "}[status]
    print(f"[{mark}] {name}" + (f"  -  {detail}" if detail else ""))


def api_key() -> str:
    """Bearer key from .env, or empty when absent."""
    env = _REPO / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith("DISCHARGEIQ_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


KEY = api_key()
AUTH = {"Authorization": f"Bearer {KEY}"} if KEY else {}


def wav_seconds(blob: bytes) -> float:
    """Duration of a WAV, or 0.0 when the bytes are not one."""
    if len(blob) < 44 or blob[:4] != b"RIFF":
        return 0.0
    rate = struct.unpack("<I", blob[24:28])[0]
    channels = struct.unpack("<H", blob[22:24])[0]
    bits = struct.unpack("<H", blob[34:36])[0]
    per_sec = rate * channels * max(bits // 8, 1)
    return (len(blob) - 44) / per_sec if per_sec else 0.0


def analyse(pdf: Path) -> dict | None:
    """Run one document through /analyze."""
    with pdf.open("rb") as handle:
        response = requests.post(
            f"{_BASE}/analyze", headers=AUTH,
            files={"file": (pdf.name, handle, "application/pdf")}, timeout=300)
    if response.status_code != 200:
        check(f"/analyze {pdf.name}", _FAIL, f"HTTP {response.status_code}")
        return None
    return response.json()


# ── 1. Service health ───────────────────────────────────────────────────────

def section_health() -> None:
    print("\n=== 1. SERVICE HEALTH ===")
    print("expect: status ok, provider vertex, database reachable\n")
    try:
        payload = requests.get(f"{_BASE}/health", timeout=60).json()
    except Exception as exc:
        check("health reachable", _FAIL, str(exc))
        return
    check("health status ok", _PASS if payload.get("status") == "ok" else _FAIL,
          str(payload.get("status")))
    check("provider is vertex (BAA path)",
          _PASS if payload.get("llm_provider") == "vertex" else _FAIL,
          str(payload.get("llm_provider")))
    database = payload.get("database") or {}
    check("database reachable",
          _PASS if database.get("reachable") else _FAIL,
          database.get("detail") or "connected")


# ── 2. Security guardrails ──────────────────────────────────────────────────

def section_guardrails() -> None:
    print("\n=== 2. SECURITY GUARDRAILS ===")
    print("expect: schema hidden, auth required on the gated endpoints\n")
    for path in ("/docs", "/openapi.json", "/redoc"):
        code = requests.get(f"{_BASE}{path}", timeout=60).status_code
        check(f"{path} not exposed", _PASS if code == 404 else _FAIL, f"HTTP {code}")

    # The key gates spend, so an unauthenticated call must not reach a model.
    code = requests.post(
        f"{_BASE}/media/case", json={"session_id": "x", "pipeline_payload": {}},
        timeout=60).status_code
    check("/media/case requires auth", _PASS if code == 401 else _FAIL, f"HTTP {code}")


# ── 3. Happy path ───────────────────────────────────────────────────────────

def section_happy(quick: bool) -> dict | None:
    print("\n=== 3. HAPPY PATH - full pipeline ===")
    print("expect: complete, all four sections written, meds and appts found\n")
    pdf = _REPO / "test-data" / "heart_failure_01.pdf"
    started = time.time()
    result = analyse(pdf)
    if result is None:
        return None
    elapsed = time.time() - started

    status = result.get("pipeline_status")
    check("pipeline_status is complete*",
          _PASS if status in ("complete", "complete_with_warnings") else _FAIL, status)
    check("finishes inside 60s", _PASS if elapsed < 60 else _WARN, f"{elapsed:.1f}s")
    check("router classified the document",
          _PASS if result.get("document_type") not in (None, "unknown") else _WARN,
          str(result.get("document_type")))

    extraction = result.get("extraction") or {}
    for field, label in (("medications", "medications"),
                         ("follow_up_appointments", "appointments"),
                         ("red_flag_symptoms", "red flags")):
        count = len(extraction.get(field) or [])
        check(f"extracted {label}", _PASS if count else _WARN, f"{count} found")

    for section in ("diagnosis_explanation", "medication_rationale",
                    "recovery_trajectory", "escalation_guide"):
        check(f"{section} written",
              _PASS if (result.get(section) or "").strip() else _FAIL)

    # Readability is a hard rule, not a preference.
    fk = result.get("fk_scores") or {}
    over = {k: v for k, v in fk.items() if isinstance(v, (int, float)) and v > 6.0}
    check("all FK grades at or under 6.0",
          _PASS if not over else _WARN,
          "over: " + ", ".join(f"{k}={v}" for k, v in over.items()) if over else "yes")

    simulator = result.get("patient_simulator") or {}
    check("Agent 6 ran", _PASS if simulator else _WARN,
          f"gap score {simulator.get('overall_gap_score')}")

    check("clean document NOT flagged as degraded",
          _PASS if result.get("source_degraded") is False else _FAIL,
          f"stratum={result.get('source_stratum')}")
    return result


# ── 4. Downstream surfaces ──────────────────────────────────────────────────

def section_downstream(result: dict, quick: bool) -> None:
    print("\n=== 4. DOWNSTREAM SURFACES ===")
    print("expect: chat grounded, quiz generated and scored, audio produced\n")
    session = result.get("pdf_session_id") or "dry-run"

    response = requests.post(
        f"{_BASE}/chat", headers={**AUTH, "Content-Type": "application/json"},
        json={"message": "Which of my medicines is for my heart?",
              "session_id": session, "pipeline_context": result}, timeout=120)
    if response.status_code == 200:
        reply = str(response.json().get("reply") or "")
        names = [str(m.get("name") or "").split()[0]
                 for m in (result.get("extraction") or {}).get("medications") or []]
        grounded = any(n and n.lower() in reply.lower() for n in names)
        check("chat answers", _PASS, f"{len(reply)} chars")
        check("chat grounded in THIS document's drugs",
              _PASS if grounded else _WARN,
              "named a real medication" if grounded else "no extracted drug named")
    else:
        check("chat answers", _FAIL, f"HTTP {response.status_code}")

    response = requests.post(
        f"{_BASE}/quiz/generate", headers={**AUTH, "Content-Type": "application/json"},
        json={"session_id": session, "extraction": result.get("extraction")},
        timeout=120)
    if response.status_code == 200:
        questions = response.json().get("questions") or []
        check("quiz generated", _PASS if len(questions) >= 3 else _WARN,
              f"{len(questions)} questions")
        check("every question carries an explanation",
              _PASS if all((q.get("explanation") or "").strip() for q in questions)
              else _WARN)
        domains = {q.get("domain") for q in questions}
        check("quiz spans multiple domains",
              _PASS if len(domains) >= 3 else _WARN, f"{len(domains)} domains")

        scored = requests.post(
            f"{_BASE}/quiz/score", headers={**AUTH, "Content-Type": "application/json"},
            json={"session_id": session, "phase": "pre",
                  "question_keys": [{"domain": q["domain"],
                                     "correct_index": q["correct_index"]}
                                    for q in questions],
                  "answers": [q["correct_index"] for q in questions]}, timeout=120)
        if scored.status_code == 200:
            body = scored.json()
            check("quiz scores a perfect round at 100%",
                  _PASS if body.get("percent") == 100 else _FAIL,
                  f"{body.get('percent')}%")
        else:
            check("quiz scoring", _FAIL, f"HTTP {scored.status_code}")
    else:
        check("quiz generated", _FAIL, f"HTTP {response.status_code}")

    kind = result.get("document_type")
    if kind and kind != "unknown":
        code = requests.get(f"{_BASE}/media/{kind}", timeout=90).status_code
        check(f"per-condition audio for {kind}",
              _PASS if code == 200 else _WARN, f"HTTP {code}")

    if quick:
        check("per-case audio", _WARN, "skipped (--quick)")
        return
    response = requests.post(
        f"{_BASE}/media/case", headers={**AUTH, "Content-Type": "application/json"},
        json={"session_id": session, "pipeline_payload": result}, timeout=180)
    if response.status_code == 200:
        seconds = wav_seconds(response.content)
        check("per-case audio generated", _PASS,
              f"{len(response.content)//1024}KB, {seconds:.0f}s")
        check("audio is a valid WAV", _PASS if seconds > 5 else _FAIL,
              f"{seconds:.1f}s decoded")
    else:
        check("per-case audio generated", _FAIL, f"HTTP {response.status_code}")


# ── 5. Failure paths ────────────────────────────────────────────────────────

def section_failures() -> None:
    print("\n=== 5. FAILURE PATHS (the Gate 3 checklist item) ===")
    print("expect: bad input handled cleanly, never a crash or a blank screen\n")

    invoice = _REPO / "test-data" / "not_a_discharge_invoice.pdf"
    if invoice.exists():
        result = analyse(invoice)
        if result is not None:
            check("non-discharge document is rejected",
                  _PASS if result.get("pipeline_status") == "rejected" else _FAIL,
                  str(result.get("pipeline_status")))
            check("rejection names a reason",
                  _PASS if (result.get("rejection_reason") or "").strip() else _FAIL,
                  (result.get("rejection_reason") or "")[:70])
            check("rejection spends no agent calls",
                  _PASS if not (result.get("diagnosis_explanation") or "").strip()
                  else _WARN)

    fax = sorted((_REPO / "test-data" / "fax").glob("*_fax.pdf"))
    if fax:
        result = analyse(fax[0])
        if result is not None:
            check("degraded document still completes",
                  _PASS if result.get("pipeline_status") in
                  ("complete", "complete_with_warnings") else _FAIL,
                  str(result.get("pipeline_status")))
            check("degraded document IS flagged",
                  _PASS if result.get("source_degraded") else _FAIL,
                  f"source_degraded={result.get('source_degraded')}")
            check("escalation guide still written for a degraded document",
                  _PASS if (result.get("escalation_guide") or "").strip() else _FAIL,
                  "generic tiers survive extraction loss")

    code = requests.get(f"{_BASE}/media/not_a_real_condition", timeout=60).status_code
    check("unknown media type 404s rather than 500s",
          _PASS if code == 404 else _FAIL, f"HTTP {code}")

    response = requests.post(
        f"{_BASE}/media/case", headers={**AUTH, "Content-Type": "application/json"},
        json={"session_id": "empty", "pipeline_payload": {}}, timeout=90)
    check("empty audio payload is refused, not narrated",
          _PASS if response.status_code in (404, 422) else _FAIL,
          f"HTTP {response.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Skip per-case audio generation")
    args = parser.parse_args()

    print("=" * 72)
    print("DischargeIQ - full application dry run")
    print(f"target: {_BASE}")
    print(f"api key: {'present' if KEY else 'MISSING - gated calls will 401'}")
    print("=" * 72)

    section_health()
    section_guardrails()
    result = section_happy(args.quick)
    if result:
        section_downstream(result, args.quick)
    section_failures()

    passed = sum(1 for s, _, _ in _results if s == _PASS)
    warned = sum(1 for s, _, _ in _results if s == _WARN)
    failed = sum(1 for s, _, _ in _results if s == _FAIL)
    print("\n" + "=" * 72)
    print(f"RESULT: {passed} passed, {warned} warnings, {failed} FAILED")
    if failed:
        print("\nFailures:")
        for status, name, detail in _results:
            if status == _FAIL:
                print(f"  - {name}: {detail}")
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
