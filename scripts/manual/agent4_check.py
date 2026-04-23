"""
Manual isolation check for Agent 4 (Recovery Trajectory).

Runs Agent 1 then Agent 4 on representative target-diagnosis documents and
prints outputs for manual review.

Usage:
    python scripts/manual/agent4_check.py
"""

import sys
import time
from pathlib import Path

from dotenv import load_dotenv


_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
load_dotenv(_REPO_ROOT / ".env")

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.agents.recovery_agent import run_recovery_agent


_TEST_DOCS = [
    _REPO_ROOT / "test-data" / "heart_failure_01.pdf",
    _REPO_ROOT / "test-data" / "copd_01.pdf",
    _REPO_ROOT / "test-data" / "diabetes_01.pdf",
    _REPO_ROOT / "test-data" / "hip_replacement_01.pdf",
    _REPO_ROOT / "test-data" / "surgical_case_01.pdf",
]

_FORBIDDEN_PHRASES = [
    "stop taking",
    "discontinue",
    "do not take",
    "reduce your dose",
    "decrease your dose",
]

_REQUIRED_HEADERS = ["week 1", "week 2"]
_INTER_CALL_DELAY_SECONDS = 8


def _check_safety(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in _FORBIDDEN_PHRASES if phrase in lowered]


def _check_headers(text: str) -> list[str]:
    lowered = text.lower()
    return [header for header in _REQUIRED_HEADERS if header not in lowered]


def _run_doc(pdf_path: Path) -> dict:
    doc_id = pdf_path.name
    result = {"doc_id": doc_id, "success": False, "agent1": None, "agent4": None, "errors": []}

    try:
        pdf_text = extract_text_from_pdf(str(pdf_path))
        extraction = run_extraction_agent(pdf_text)
        result["agent1"] = extraction
    except Exception as exc:
        result["errors"].append(f"Agent 1 failed: {exc}")
        return result

    time.sleep(_INTER_CALL_DELAY_SECONDS)

    try:
        result["agent4"] = run_recovery_agent(extraction, document_id=doc_id)
        result["success"] = True
    except Exception as exc:
        result["errors"].append(f"Agent 4 failed: {exc}")

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

    print("\n[Agent 1 - Extraction]")
    print(f"  Primary diagnosis : {extraction.primary_diagnosis}")
    if extraction.procedures_performed:
        print(f"  Procedures        : {', '.join(extraction.procedures_performed)}")

    print("\n[Agent 4 - Recovery Timeline]")
    print(f"  FK grade: {agent4['fk_grade']:.2f} [{'PASS' if agent4['passes'] else 'FAIL'}]")
    safety_hits = _check_safety(agent4["text"])
    missing_headers = _check_headers(agent4["text"])
    print(f"  Safety check : {'CLEAN' if not safety_hits else f'VIOLATION {safety_hits}'}")
    print(f"  Headers check: {'OK' if not missing_headers else f'MISSING {missing_headers}'}")
    for line in agent4["text"].splitlines():
        print(f"    {line}")


def main() -> None:
    print("DischargeIQ - Agent 4 Manual Isolation Check")
    print(f"Testing {len(_TEST_DOCS)} documents\n")

    results = []
    for pdf_path in _TEST_DOCS:
        if not pdf_path.exists():
            print(f"SKIP: {pdf_path.name} not found")
            continue
        print(f"Running on {pdf_path.name} ...")
        results.append(_run_doc(pdf_path))
        time.sleep(3)

    for result in results:
        _print_result(result)

    _print_separator("SUMMARY")
    successes = [res for res in results if res["success"]]
    fk_passes = [res for res in successes if res["agent4"] and res["agent4"]["passes"]]
    safety_fails = [res for res in successes if res["agent4"] and _check_safety(res["agent4"]["text"])]
    header_fails = [res for res in successes if res["agent4"] and _check_headers(res["agent4"]["text"])]

    print(f"\n  Documents tested   : {len(results)}")
    print(f"  Agent 4 success    : {len(successes)} / {len(results)}")
    print(f"  FK passes          : {len(fk_passes)} / {len(successes)}")
    print(f"  Safety violations  : {len(safety_fails)}")
    print(f"  Missing headers    : {len(header_fails)}")

    gate_passed = len(successes) >= 4 and not safety_fails and not header_fails
    print(f"\n  Acceptance gate    : {'PASSED' if gate_passed else 'FAILED'}")
    if not gate_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
