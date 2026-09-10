#!/usr/bin/env python3
"""
scripts/e2e_journey.py

Walk one patient's complete journey through the deployed service, in the order
a real patient does it. Owner: Likitha Shankar.

HOW THIS DIFFERS FROM scripts/dry_run.py
----------------------------------------
dry_run.py checks that each endpoint works. This checks that the JOURNEY
works: that what one step produces is usable by the next, that every tab the
app renders has something in it, and that the teach-back loop actually
measures a delta rather than merely returning 200 twice.

An endpoint suite passes when the parts work. A journey fails when the parts
work and the seams do not - a session id the next call rejects, a quiz that
scores but never produces a lift number, a tab with nothing in it.

Runs against several diagnoses because agent behaviour varies by document,
and a single happy path proves less than it appears to.

Usage:
  python scripts/e2e_journey.py
  python scripts/e2e_journey.py --docs heart_failure_01 copd_01
"""

import argparse
import struct
import sys
import time
from pathlib import Path

import requests

_REPO = Path(__file__).resolve().parent.parent
_BASE = "https://dischargeiq-678599658918.us-central1.run.app/api"

_results: list[tuple[bool, str, str]] = []


def step(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((ok, name, detail))
    print(f"    [{'ok  ' if ok else 'FAIL'}] {name}" + (f"  -  {detail}" if detail else ""))
    return ok


def api_key() -> str:
    env = _REPO / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        if line.startswith("DISCHARGEIQ_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


KEY = api_key()
AUTH = {"Authorization": f"Bearer {KEY}"}
JSON_AUTH = {**AUTH, "Content-Type": "application/json"}


def journey(doc: str) -> None:
    """One patient, start to finish."""
    print(f"\n--- {doc} " + "-" * (58 - len(doc)))
    pdf = _REPO / "test-data" / f"{doc}.pdf"
    if not pdf.exists():
        step(False, "document exists", str(pdf))
        return

    # 1. Upload, the way the app does.
    started = time.time()
    with pdf.open("rb") as handle:
        response = requests.post(
            f"{_BASE}/analyze", headers=AUTH,
            files={"file": (pdf.name, handle, "application/pdf")}, timeout=300)
    if not step(response.status_code == 200, "upload analysed",
                f"HTTP {response.status_code}, {time.time() - started:.1f}s"):
        return
    result = response.json()
    session = result.get("pdf_session_id") or ""

    status = result.get("pipeline_status")
    step(status in ("complete", "complete_with_warnings"), "pipeline finished", status)

    # 2. Every tab the app renders must have something to render.
    #    A blank tab is the failure a patient actually experiences.
    extraction = result.get("extraction") or {}
    tabs = {
        "What happened": (result.get("diagnosis_explanation") or "").strip(),
        "Medications": (result.get("medication_rationale") or "").strip(),
        "Recovery": (result.get("recovery_trajectory") or "").strip(),
        "Warning signs": (result.get("escalation_guide") or "").strip(),
        "Appointments": extraction.get("follow_up_appointments") or [],
        "Discharge Check": result.get("patient_simulator") or {},
    }
    for tab, content in tabs.items():
        step(bool(content), f"tab has content: {tab}",
             f"{len(content)} chars" if isinstance(content, str) else f"{len(content)} items")

    # 3. The PDF seam, both halves.
    #
    #    This assertion used to be "fetchable by session id", and it passed
    #    because the session id alone WAS enough - which was the
    #    vulnerability. The test encoded the bug as the expected behaviour,
    #    and only failed once the bug was fixed. Worth remembering: a test
    #    written against current behaviour ratifies whatever that behaviour
    #    is, including the parts nobody meant.
    token = result.get("pdf_token")
    exp = result.get("pdf_token_exp")
    step(bool(token and exp), "analyze issued a signed PDF token",
         f"expires {exp}")

    signed = requests.get(f"{_BASE}/pdf/{session}",
                          params={"token": token, "exp": exp}, timeout=60)
    step(signed.status_code == 200 and signed.content[:4] == b"%PDF",
         "PDF fetchable WITH the signed token",
         f"HTTP {signed.status_code}, {len(signed.content)} bytes")

    unsigned = requests.get(f"{_BASE}/pdf/{session}", timeout=60)
    step(unsigned.status_code == 404,
         "PDF NOT fetchable without it",
         f"HTTP {unsigned.status_code}")

    # 4. Chat, grounded in THIS document rather than in general knowledge.
    chat = requests.post(
        f"{_BASE}/chat", headers=JSON_AUTH,
        json={"message": "Which medicine helps my heart?",
              "session_id": session, "pipeline_context": result}, timeout=120)
    if step(chat.status_code == 200, "chat answers", f"HTTP {chat.status_code}"):
        reply = str(chat.json().get("reply") or "")
        drugs = [str(m.get("name") or "").split()[0]
                 for m in extraction.get("medications") or []]
        step(any(d and d.lower() in reply.lower() for d in drugs) or not drugs,
             "chat names a drug from THIS document",
             f"{len(reply)} chars")

    # 5. The teach-back loop, both halves. Scoring twice is not the test -
    #    producing a comprehension delta between them is.
    quiz = requests.post(
        f"{_BASE}/quiz/generate", headers=JSON_AUTH,
        json={"session_id": session, "extraction": extraction}, timeout=120)
    if not step(quiz.status_code == 200, "quiz generated", f"HTTP {quiz.status_code}"):
        return
    questions = quiz.json().get("questions") or []
    step(len(questions) >= 3, "quiz has enough questions", f"{len(questions)}")

    keys = [{"domain": q["domain"], "correct_index": q["correct_index"]}
            for q in questions]

    # Baseline: deliberately wrong, the way a patient who has not read it does.
    wrong = [(q["correct_index"] + 1) % len(q["options"]) for q in questions]
    pre = requests.post(f"{_BASE}/quiz/score", headers=JSON_AUTH,
                        json={"session_id": session, "phase": "pre",
                              "question_keys": keys, "answers": wrong}, timeout=120)
    pre_pct = pre.json().get("percent") if pre.status_code == 200 else None
    step(pre.status_code == 200, "baseline scored", f"{pre_pct}%")

    # After the learning cards: all correct.
    right = [q["correct_index"] for q in questions]
    post = requests.post(f"{_BASE}/quiz/score", headers=JSON_AUTH,
                         json={"session_id": session, "phase": "post",
                               "question_keys": keys, "answers": right}, timeout=120)
    if step(post.status_code == 200, "post-teaching scored",
            f"{post.json().get('percent') if post.status_code == 200 else '-'}%"):
        body = post.json()
        delta = body.get("comprehension_delta")
        step(delta is not None, "comprehension delta computed server-side",
             f"delta={delta}")
        step(body.get("percent") == 100, "perfect answers score 100%",
             f"{body.get('percent')}%")

    # 6. Audio, both kinds.
    #
    #    /media/case is capped at 4 requests per minute per IP by our own
    #    limiter. A run that trips it reports "audio broken" when the service
    #    is fine - the same false alarm predemo.sh produced on /analyze. A
    #    sub-second 429 is ours; wait out the window and try once more.
    audio = requests.post(f"{_BASE}/media/case", headers=JSON_AUTH,
                          json={"session_id": session, "pipeline_payload": result},
                          timeout=180)
    if audio.status_code == 429:
        print("      (local rate limit on /media/case, waiting 60s)")
        time.sleep(60)
        audio = requests.post(f"{_BASE}/media/case", headers=JSON_AUTH,
                              json={"session_id": session,
                                    "pipeline_payload": result}, timeout=180)
    if step(audio.status_code == 200, "per-case audio generated",
            f"{len(audio.content) // 1024} KB"):
        blob = audio.content
        rate = struct.unpack("<I", blob[24:28])[0] if blob[:4] == b"RIFF" else 0
        step(rate > 0 and (len(blob) - 44) / (rate * 2) > 5,
             "audio is a playable WAV",
             f"{(len(blob) - 44) / (rate * 2):.0f}s" if rate else "not a WAV")

    kind = result.get("document_type")
    if kind and kind != "unknown":
        podcast = requests.get(f"{_BASE}/media/{kind}", timeout=90)
        step(podcast.status_code == 200, f"per-condition audio ({kind})",
             f"{len(podcast.content) // 1024} KB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", nargs="*",
                        default=["heart_failure_01", "copd_01", "hip_replacement_01"])
    args = parser.parse_args()

    print("=" * 70)
    print("DischargeIQ - full patient journey")
    print(f"target: {_BASE}")
    print("=" * 70)

    for i, doc in enumerate(args.docs):
        journey(doc)
        # /analyze is capped at 5/min per IP by our own limiter; pace so the
        # run measures the service rather than the limiter.
        if i < len(args.docs) - 1:
            time.sleep(20)

    passed = sum(1 for ok, _, _ in _results if ok)
    failed = len(_results) - passed
    print("\n" + "=" * 70)
    print(f"RESULT: {passed} passed, {failed} FAILED")
    for ok, name, detail in _results:
        if not ok:
            print(f"  - {name}: {detail}")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
