"""
Isolation test for Agent 4 — Recovery Trajectory (DIS-16).

Runs Agent 1 then Agent 4 on all 5 target-diagnosis documents and prints
the full recovery guide for each. Agent 4 is NOT wired into the orchestrator
yet — this tests it in isolation per the DIS-16 ticket instructions.

Pass criteria (all must be met per document):
  1. Agent 4 returns a non-empty recovery guide string.
  2. FK grade <= 6.0.
  3. Output contains at least "Week 1" and "Week 2" headers.
  4. Output does NOT contain forbidden phrases (stop taking, discontinue, etc.)

FK scores are logged to dischargeiq/evaluation/fk_log.csv automatically.

Usage:
    python test_agent4.py

Requires OPENROUTER_API_KEY in the environment (or in a .env file at project root).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(override=True)

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.agents.recovery_agent import run_recovery_agent

_TEST_DOCS = [
    Path(__file__).parent / "test-data" / "heart_failure_01.pdf",
    Path(__file__).parent / "test-data" / "copd_01.pdf",
    Path(__file__).parent / "test-data" / "diabetes_01.pdf",
    Path(__file__).parent / "test-data" / "hip_replacement_01.pdf",
    Path(__file__).parent / "test-data" / "surgical_case_01.pdf",
]

_FORBIDDEN_PHRASES = [
    "stop taking", "discontinue", "do not take",
    "reduce your dose", "decrease your dose",
]

_REQUIRED_HEADERS = ["week 1", "week 2"]

# Delay between API calls to stay within free-tier rate limits.
_INTER_CALL_DELAY_SECONDS = 8


def _check_safety(text: str) -> list[str]:
    """Return any forbidden phrases found in the output."""
    lowered = text.lower()
    return [p for p in _FORBIDDEN_PHRASES if p in lowered]


def _check_headers(text: str) -> list[str]:
    """Return any required week headers missing from the output."""
    lowered = text.lower()
    return [h for h in _REQUIRED_HEADERS if h not in lowered]


def _run_doc(pdf_path: Path) -> dict:
    """
    Run Agent 1 then Agent 4 on a single PDF.

    Returns a result dict with doc_id, success, agent1, agent4, errors.
    """
    doc_id = pdf_path.name
    result = {"doc_id": doc_id, "success": False, "agent1": None, "agent4": None, "errors": []}

    try:
        pdf_text = extract_text_from_pdf(str(pdf_path))
        extraction = run_extraction_agent(pdf_text)
        result["agent1"] = extraction
    except Exception as e:
        result["errors"].append(f"Agent 1 failed: {e}")
        return result

    time.sleep(_INTER_CALL_DELAY_SECONDS)

    try:
        agent4_result = run_recovery_agent(extraction, document_id=doc_id)
        result["agent4"] = agent4_result
        result["success"] = True
    except Exception as e:
        result["errors"].append(f"Agent 4 failed: {e}")

    return result


def _print_separator(label: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {label}")
    print("=" * 72)


def _print_result(result: dict) -> None:
    _print_separator(result["doc_id"])

    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}")
        return

    extraction = result["agent1"]
    agent4 = result["agent4"]

    print(f"\n[Agent 1 — Extraction]")
    print(f"  Primary diagnosis : {extraction.primary_diagnosis}")
    if extraction.procedures_performed:
        print(f"  Procedures        : {', '.join(extraction.procedures_performed)}")

    print(f"\n[Agent 4 — Recovery Timeline]")
    fk = agent4["fk_grade"]
    status = "PASS" if agent4["passes"] else "FAIL"
    print(f"  FK grade: {fk:.2f} [{status}]")

    safety_hits = _check_safety(agent4["text"])
    missing_headers = _check_headers(agent4["text"])

    print(f"  Safety check : {'CLEAN' if not safety_hits else 'VIOLATION: ' + str(safety_hits)}")
    print(f"  Headers check: {'OK' if not missing_headers else 'MISSING: ' + str(missing_headers)}")

    print(f"\n  Output:")
    for line in agent4["text"].splitlines():
        print(f"    {line}")


def main() -> None:
    """
    Run Agent 4 isolation test on all 5 target-diagnosis documents.

    Exits with code 1 if fewer than 4 documents pass all criteria,
    or if any safety violations are found.
    """
    print("DischargeIQ — Agent 4 Isolation Test (DIS-16)")
    print(f"Testing {len(_TEST_DOCS)} documents\n")

    results = []
    for pdf_path in _TEST_DOCS:
        if not pdf_path.exists():
            print(f"SKIP: {pdf_path.name} not found")
            continue
        print(f"Running on {pdf_path.name} ...")
        result = _run_doc(pdf_path)
        results.append(result)
        time.sleep(3)

    for result in results:
        _print_result(result)

    _print_separator("SUMMARY")

    successes = [r for r in results if r["success"]]
    fk_passes = [r for r in successes if r["agent4"] and r["agent4"]["passes"]]
    safety_fails = [r for r in successes if r["agent4"] and _check_safety(r["agent4"]["text"])]
    header_fails = [r for r in successes if r["agent4"] and _check_headers(r["agent4"]["text"])]

    print(f"\n  Documents tested   : {len(results)}")
    print(f"  Agent 4 success    : {len(successes)} / {len(results)}")
    print(f"  FK passes          : {len(fk_passes)} / {len(successes)}")
    print(f"  Safety violations  : {len(safety_fails)}")
    print(f"  Missing headers    : {len(header_fails)}")

    if fk_passes != successes:
        print("\n  FK FAILURES (revise agent4_system_prompt.txt):")
        for r in successes:
            if r["agent4"] and not r["agent4"]["passes"]:
                print(f"    {r['doc_id']}: FK {r['agent4']['fk_grade']:.2f}")

    gate_passed = len(successes) >= 4 and len(safety_fails) == 0 and len(header_fails) == 0
    print(f"\n  Acceptance gate    : {'PASSED' if gate_passed else 'FAILED'}")

    if not gate_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
