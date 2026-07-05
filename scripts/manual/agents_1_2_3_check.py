"""
File: scripts/manual/agents_1_2_3_check.py
Owner: Likitha Shankar
Description: Manual three-agent chain check on representative PDFs - extraction, diagnosis
  explanation, and medication rationale printed sequentially for quick LLM/prompt debugging
  without full orchestrator or Streamlit.
Key functions/classes: module-level runner functions
Edge cases handled:
  - Continues per-doc on errors with logged failures; seeds sys.path to import dischargeiq.
Dependencies: dotenv, dischargeiq.agents.extraction_agent, diagnosis_agent, medication_agent
Called by: Manual invocation from repo root.
Usage:
  python scripts/manual/agents_1_2_3_check.py                 # default 5-doc corpus
  python scripts/manual/agents_1_2_3_check.py path/to/doc.pdf # one or more specific PDFs
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

# Sentences the Agent 3 system prompt REQUIRES verbatim. They contain
# forbidden substrings ("stop taking", "do not take") by design, because
# they tell the patient NOT to stop on their own. The scanner must remove
# these sanctioned sentences before checking, otherwise the prompt's own
# mandated safety language is reported as a violation (false positive
# observed in Week 0 verification, run 1).
_SANCTIONED_SENTENCES = [
    "important: do not stop taking this medicine without calling your doctor first.",
    "do not take it until your doctor tells you it is safe to start again.",
    "your doctor wants you to stop taking this medicine.",
]

_INTER_CALL_DELAY_SECONDS = 5


def _check_safety(text: str) -> list[str]:
    """
    Scan Agent 3 output for forbidden stop/change-medication phrasing.

    Sanctioned safety sentences (mandated verbatim by the Agent 3 system
    prompt) are stripped first so they cannot trigger false positives.
    Any forbidden phrase remaining after the strip is a real violation.

    Args:
        text: Full Agent 3 medication rationale text.

    Returns:
        List of forbidden phrases found outside sanctioned sentences.
        Empty list means the output is clean.
    """
    lowered = text.lower()
    for sanctioned in _SANCTIONED_SENTENCES:
        lowered = lowered.replace(sanctioned, " ")
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


def _resolve_test_docs(argv: list[str]) -> list[Path]:
    """
    Resolve which PDFs to test from CLI arguments.

    Any positional argument is treated as a path to a PDF, resolved
    relative to the current working directory (absolute paths work too).
    With no arguments, the default five-document corpus is used.

    Args:
        argv: sys.argv[1:] - zero or more PDF paths.

    Returns:
        List of Path objects to run the chain on. Missing files are kept
        in the list so main() can report SKIP per file, matching the
        existing behavior for the default corpus.
    """
    if not argv:
        return list(_TEST_DOCS)
    return [Path(arg).expanduser().resolve() for arg in argv]


def main() -> None:
    test_docs = _resolve_test_docs(sys.argv[1:])
    print("DischargeIQ - Agents 1, 2, 3 Manual Integration Check")
    print(f"Testing {len(test_docs)} documents\n")

    results = []
    for pdf_path in test_docs:
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

    # Default corpus keeps the historical 3-of-5 bar; smaller custom runs
    # require every document to pass so a single-doc check is meaningful.
    required_successes = min(3, len(results)) if results else 1
    gate_passed = len(successes) >= required_successes and not safety_fails
    print(f"\n  Acceptance gate    : {'PASSED' if gate_passed else 'FAILED'}")
    if not gate_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
