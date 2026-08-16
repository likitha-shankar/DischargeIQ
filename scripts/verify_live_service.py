#!/usr/bin/env python3
"""
scripts/verify_live_service.py

End-to-end verification of the DEPLOYED service, from the outside.
Owner: Likitha Shankar.

Why this exists separately from the pytest suite: the suite runs against a
FastAPI TestClient with mocked agents, so it proves the code is internally
consistent. It cannot tell you whether the thing patients actually reach is
gated, grounded, readable, and awake. Both of the real defects found on
15 Aug 2026 - an ungated chat endpoint and a diagnosis section above the
reading target - were invisible to the suite and obvious from out here.

Run it before every checkpoint demo, and after every deploy:

    python scripts/verify_live_service.py                  # full run
    python scripts/verify_live_service.py --guardrails     # no LLM spend
    python scripts/verify_live_service.py --url http://127.0.0.1:8000

Cost: the full run performs two analyses, one chat pair and one quiz cycle,
roughly fifteen LLM calls. --guardrails costs nothing and is safe to run on a
demo morning.

Requires DISCHARGEIQ_API_KEY in .env (the same key the phone carries).
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_DEFAULT_URL = "https://dischargeiq-678599658918.us-central1.run.app"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_FK_TARGET = 6.0


class Report:
    """Tally of checks, so the exit code means something to CI or a shell."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        """Record one check and print it in a fixed-width, greppable form."""
        if ok:
            self.passed += 1
            print(f"  PASS  {name:52s} {detail}")
        else:
            self.failed += 1
            print(f"  FAIL  {name:52s} {detail}")


def _api_key() -> str:
    """Read the bearer key from .env, the same source the deploy script uses."""
    env = _REPO_ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith("DISCHARGEIQ_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


class Client:
    """Minimal HTTP client. Deliberately stdlib-only so this script has no deps."""

    def __init__(self, base: str, key: str) -> None:
        self.base = base.rstrip("/")
        self.key = key

    def _headers(self, authed: bool, content_type: str | None = None) -> dict:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        if authed and self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        return headers

    def post_json(self, path: str, body: dict, authed: bool = True,
                  timeout: int = 180) -> tuple[int, dict | None]:
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode(),
            headers=self._headers(authed, "application/json"))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as exc:
            return exc.code, None

    def post_pdf(self, path: str, pdf: Path,
                 timeout: int = 300) -> tuple[int, dict | None]:
        boundary = "----dischargeiqverify"
        payload = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{pdf.name}"\r\nContent-Type: application/pdf\r\n\r\n'
        ).encode() + pdf.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            self.base + path, data=payload,
            headers=self._headers(True, f"multipart/form-data; boundary={boundary}"))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as exc:
            return exc.code, None

    def get(self, path: str, authed: bool = True,
            timeout: int = 60) -> tuple[int, bytes]:
        req = urllib.request.Request(self.base + path, headers=self._headers(authed))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, b""


def run_guardrails(client: Client, report: Report) -> None:
    """
    Checks that cost nothing: liveness, the spend gate, and the API surface.

    The spend gate is the one that matters financially - every route below
    that reaches an LLM must refuse an unauthenticated caller. /chat is the
    documented exception (the browser panel calls it), but it must still
    refuse a caller who invents their own grounding context, which is how it
    was being abused before 15 Aug 2026.
    """
    print("== liveness ==")
    status, body = client.get("/api/health", authed=False)
    report.check("GET /api/health", status == 200, str(status))
    report.check("health reports ok", b'"status":"ok"' in body)

    print("== spend gate ==")
    for path, payload in (("/api/analyze", None),
                          ("/api/quiz/generate", {}),
                          ("/api/quiz/score", {})):
        if payload is None:
            code, _ = client.post_json(path, {}, authed=False, timeout=30)
        else:
            code, _ = client.post_json(path, payload, authed=False, timeout=30)
        report.check(f"POST {path} without a key", code == 401, str(code))

    code, _ = client.post_json("/api/chat", {
        "message": "what are my medicines",
        "session_id": "verify-anonymous",
        "pipeline_context": {"extraction": {"primary_diagnosis": "Invented"}},
    }, authed=False, timeout=60)
    report.check("POST /api/chat with invented context, no key", code == 401, str(code))

    print("== API surface stays closed ==")
    for path in ("/api/docs", "/api/openapi.json", "/api/redoc"):
        code, _ = client.get(path, authed=False)
        report.check(f"GET {path}", code == 404, str(code))


def run_journey(client: Client, report: Report) -> None:
    """
    The path a patient actually walks, in order, against the live service.

    Each step depends on the one before it, so a failure early is reported and
    the rest is skipped rather than producing a cascade of misleading failures.
    """
    pdf = _REPO_ROOT / "test-data" / "heart_failure_01.pdf"
    print("== analyze ==")
    started = time.time()
    status, result = client.post_pdf("/api/analyze", pdf)
    report.check("POST /api/analyze", status == 200,
                 f"{status} in {time.time() - started:.0f}s")
    if status != 200 or not result:
        print("  (skipping the rest: no analysis to work from)")
        return

    session = result.get("pdf_session_id")
    report.check("pipeline_status is a success state",
                 result.get("pipeline_status") in ("complete", "complete_with_warnings"),
                 str(result.get("pipeline_status")))
    for field in ("diagnosis_explanation", "medication_rationale",
                  "recovery_trajectory", "escalation_guide"):
        report.check(f"{field} present", bool(str(result.get(field) or "").strip()))
    report.check("agent 6 ran", result.get("patient_simulator") is not None)

    print("== readability, every section of one document ==")
    for agent, grade in sorted(
            (a, (v or {}).get("fk_grade")) for a, v in (result.get("fk_scores") or {}).items()):
        if isinstance(grade, (int, float)):
            report.check(f"{agent} at or under {_FK_TARGET}", grade <= _FK_TARGET,
                         f"grade {grade}")

    print("== recovery weeks are not collapsed into ranges ==")
    weeks = [h for h in re.findall(r"\*\*([^*]+)\*\*",
                                   str(result.get("recovery_trajectory") or ""))
             if h.lower().startswith("week")]
    report.check("no combined week range",
                 not any(re.search(r"\d\s*-\s*\d", w) for w in weeks), ", ".join(weeks))

    print("== original document ==")
    status, blob = client.get(f"/api/pdf/{session}")
    report.check("GET /api/pdf/{session}", status == 200, f"{status}, {len(blob)} bytes")
    report.check("returns a real PDF", blob[:4] == b"%PDF")

    print("== grounded chat ==")
    status, chat = client.post_json("/api/chat",
                                    {"message": "What medicines do I take?",
                                     "session_id": session})
    report.check("chat answers from the cached session", status == 200, str(status))
    if chat:
        report.check("answer is grounded", chat.get("from_document") is True)
    _, off = client.post_json("/api/chat", {
        "message": "What was my blood pressure on day three of my stay?",
        "session_id": session})
    if off:
        report.check("a question the document cannot answer is not claimed as grounded",
                     off.get("from_document") is False)

    status, _ = client.post_json("/api/chat", {"message": "What medicines do I take?",
                                               "session_id": "someone-elses-session"})
    report.check("another patient's session is not readable", status == 409, str(status))

    print("== teach-back loop ==")
    status, quiz = client.post_json("/api/quiz/generate",
                                    {"session_id": session,
                                     "extraction": result["extraction"]})
    report.check("POST /quiz/generate", status == 200, str(status))
    if quiz:
        questions = quiz.get("questions") or []
        report.check("quiz has 3 to 5 questions", 3 <= len(questions) <= 5,
                     f"{len(questions)}")
        keys = [{"domain": q["domain"], "correct_index": q["correct_index"]}
                for q in questions]
        _, pre = client.post_json("/api/quiz/score", {
            "session_id": session, "phase": "pre", "question_keys": keys,
            "answers": [(q["correct_index"] + 1) % 4 for q in questions]})
        _, post = client.post_json("/api/quiz/score", {
            "session_id": session, "phase": "post", "question_keys": keys,
            "answers": [q["correct_index"] for q in questions]})
        if pre and post:
            report.check("deliberately wrong pre-quiz scores 0", pre.get("score") == 0)
            report.check("correct post-quiz scores 100", post.get("percent") == 100.0)
            report.check("server computes the comprehension delta",
                         post.get("comprehension_delta") is not None,
                         f"delta={post.get('comprehension_delta')}")

    print("== a document that is not a discharge summary ==")
    invoice = _REPO_ROOT / "test-data" / "not_a_discharge_invoice.pdf"
    if invoice.exists():
        status, rejected = client.post_pdf("/api/analyze", invoice)
        report.check("invoice is rejected, not analysed",
                     status == 200 and (rejected or {}).get("pipeline_status") == "rejected",
                     str((rejected or {}).get("pipeline_status")))
        report.check("rejection carries a reason for the patient",
                     bool((rejected or {}).get("rejection_reason")))


def main() -> None:
    """Parse arguments, run the selected checks, exit non-zero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=_DEFAULT_URL, help="Service base URL")
    parser.add_argument("--guardrails", action="store_true",
                        help="Only the checks that spend no LLM calls")
    args = parser.parse_args()

    key = _api_key()
    if not key:
        print("WARNING: no DISCHARGEIQ_API_KEY in .env - gated checks will misreport")

    client = Client(args.url, key)
    report = Report()
    print(f"verifying {args.url}\n")
    run_guardrails(client, report)
    if not args.guardrails:
        run_journey(client, report)

    print(f"\n{report.passed} passed, {report.failed} failed")
    sys.exit(1 if report.failed else 0)


if __name__ == "__main__":
    main()
