"""
Manual integration check for Agents 1, 2, and 3.

Runs PDF -> Agent 1 (extraction) -> Agent 2 (diagnosis explanation) ->
Agent 3 (medication rationale) on a representative test-data subset and
prints structured results for human review.

Usage:
    python scripts/manual/agents_1_2_3_check.py
"""

import sys
import time
from pathlib import Path

from dotenv import load_dotenv


_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
load_dotenv(_REPO_ROOT / ".env")

from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent
from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.agents.medication_agent import run_medication_agent


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
    "skip your",
    "avoid taking",
]

_INTER_CALL_DELAY_SECONDS = 5


def _check_safety(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in _FORBIDDEN_PHRASES if phrase in lowered]


def _run_chain(pdf_path: Path) -> dict:
    doc_id = pdf_path.name
    result = {
        "doc_id": doc_id,
        "success": False,
        "agent1": None,
        "agent2": None,
        "agent3": None,
        "errors": [],
    }
    try:
        pdf_text = extract_text_from_pdf(str(pdf_path))
        extraction = run_extraction_agent(pdf_text)
        result["agent1"] = extraction
    except Exception as exc:
        result["errors"].append(f"Agent 1 failed: {exc}")
        return result

    time.sleep(_INTER_CALL_DELAY_SECONDS)

    try:
        result["agent2"] = run_diagnosis_agent(extraction, document_id=doc_id)
    except Exception as exc:
        result["errors"].append(f"Agent 2 failed: {exc}")
        return result

    time.sleep(_INTER_CALL_DELAY_SECONDS)

    try:
        result["agent3"] = run_medication_agent(extraction, document_id=doc_id)
    except Exception as exc:
        result["errors"].append(f"Agent 3 failed: {exc}")
        return result

    result["success"] = True
    return result


def _print_separator(label: str) -> None:
    width = 72
    print("\n" + "=" * width)
    print(f"  {label}")
    print("=" * width)


def _print_result(result: dict) -> None:
    _print_separator(result["doc_id"])

    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}")
        return

    extraction = result["agent1"]
    agent2 = result["agent2"]
    agent3 = result["agent3"]

    print("\n[Agent 1 - Extraction]")
    print(f"  Primary diagnosis : {extraction.primary_diagnosis}")
    print(f"  Medications found : {len(extraction.medications)}")
    for med in extraction.medications:
        dose = f" {med.dose}" if med.dose else ""
        freq = f", {med.frequency}" if med.frequency else ""
        print(f"    - {med.name}{dose}{freq}")
    if extraction.extraction_warnings:
        for warning in extraction.extraction_warnings:
            print(f"  WARNING: {warning}")

    print("\n[Agent 2 - Diagnosis Explanation]")
    print(f"  FK grade: {agent2['fk_grade']:.2f} [{'PASS' if agent2['passes'] else 'FAIL'}]")
    for line in agent2["text"].splitlines():
        print(f"    {line}")

    print("\n[Agent 3 - Medication Rationale]")
    print(f"  FK grade: {agent3['fk_grade']:.2f} [{'PASS' if agent3['passes'] else 'FAIL'}]")
    violations = _check_safety(agent3["text"])
    print(f"  Safety check: {'CLEAN' if not violations else f'VIOLATION {violations}'}")
    for line in agent3["text"].splitlines():
        print(f"    {line}")


def main() -> None:
    print("DischargeIQ - Agents 1, 2, 3 Manual Integration Check")
    print(f"Testing {len(_TEST_DOCS)} documents\n")

    results = []
    for pdf_path in _TEST_DOCS:
        if not pdf_path.exists():
            print(f"SKIP: {pdf_path.name} not found")
            continue
        print(f"Running chain on {pdf_path.name} ...")
        results.append(_run_chain(pdf_path))
        time.sleep(2)

    for result in results:
        _print_result(result)

    _print_separator("SUMMARY")
    successes = [res for res in results if res["success"]]
    safety_fails = [
        res for res in successes
        if res["agent3"] and _check_safety(res["agent3"]["text"])
    ]
    print(f"\n  Documents tested   : {len(results)}")
    print(f"  Full chain success : {len(successes)} / {len(results)}")
    print(f"  Safety violations  : {len(safety_fails)}")

    gate_passed = len(successes) >= 3 and not safety_fails
    print(f"\n  Acceptance gate    : {'PASSED' if gate_passed else 'FAILED'}")
    if not gate_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
