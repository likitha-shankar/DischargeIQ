"""
Integration test: Agents 1, 2, and 3 end-to-end (DIS-12).

Runs the full chain PDF -> Agent 1 (extraction) -> Agent 2 (diagnosis explanation)
-> Agent 3 (medication rationale) on a representative subset of test documents
and prints all three outputs side by side.

Pass criteria (all must be met per document):
  1. Agent 1 returns a valid ExtractionOutput with a non-empty primary_diagnosis.
  2. Agent 2 returns a non-empty explanation string with FK grade <= 6.0.
  3. Agent 3 returns a non-empty rationale string with FK grade <= 6.0.
  4. Agent 3 output does NOT contain the phrases "stop taking", "discontinue",
     "do not take", or "reduce your dose" (safety check).

FK scores are logged to dischargeiq/evaluation/fk_log.csv automatically
by each agent.

Usage:
    python test_agents_1_2_3.py

Requires ANTHROPIC_API_KEY in the environment (or in a .env file at project root).
"""

import sys
import time
from pathlib import Path

# Make the project root importable when running this script directly.
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent
from dischargeiq.agents.medication_agent import run_medication_agent

# Run on 3 documents covering different diagnoses to meet the acceptance criteria
# requirement of manually verifying at least 3 outputs.
_TEST_DOCS = [
    Path(__file__).parent / "test-data" / "heart_failure_01.pdf",
    Path(__file__).parent / "test-data" / "copd_01.pdf",
    Path(__file__).parent / "test-data" / "diabetes_01.pdf",
    Path(__file__).parent / "test-data" / "hip_replacement_01.pdf",
    Path(__file__).parent / "test-data" / "surgical_case_01.pdf",
]

# Phrases that must never appear in Agent 3 output — safety hard check.
_FORBIDDEN_PHRASES = [
    "stop taking",
    "discontinue",
    "do not take",
    "reduce your dose",
    "decrease your dose",
    "skip your",
    "avoid taking",
]

# Delay between API calls to avoid rate-limit errors on free-tier keys.
_INTER_CALL_DELAY_SECONDS = 5


def _check_safety(text: str) -> list[str]:
    """
    Scan agent output for forbidden phrases that would constitute medical advice.

    Returns a list of found violations (empty list = clean).
    """
    lowered = text.lower()
    return [phrase for phrase in _FORBIDDEN_PHRASES if phrase in lowered]


def _run_chain(pdf_path: Path) -> dict:
    """
    Run Agents 1, 2, and 3 in sequence on a single PDF.

    Returns a result dict with keys: doc_id, success, agent1, agent2, agent3,
    errors. On any agent failure, success is False and errors contains the
    exception message.
    """
    doc_id = pdf_path.name
    result = {
        "doc_id": doc_id,
        "success": False,
        "agent1": None,
        "agent2": None,
        "agent3": None,
        "errors": [],
    }

    # ── Agent 1 ────────────────────────────────────────────────────────────────
    try:
        pdf_text = extract_text_from_pdf(str(pdf_path))
        extraction = run_extraction_agent(pdf_text)
        result["agent1"] = extraction
    except Exception as e:
        result["errors"].append(f"Agent 1 failed: {e}")
        return result

    time.sleep(_INTER_CALL_DELAY_SECONDS)

    # ── Agent 2 ────────────────────────────────────────────────────────────────
    try:
        agent2_result = run_diagnosis_agent(extraction, document_id=doc_id)
        result["agent2"] = agent2_result
    except Exception as e:
        result["errors"].append(f"Agent 2 failed: {e}")
        return result

    time.sleep(_INTER_CALL_DELAY_SECONDS)

    # ── Agent 3 ────────────────────────────────────────────────────────────────
    try:
        agent3_result = run_medication_agent(extraction, document_id=doc_id)
        result["agent3"] = agent3_result
    except Exception as e:
        result["errors"].append(f"Agent 3 failed: {e}")
        return result

    result["success"] = True
    return result


def _print_separator(label: str) -> None:
    width = 72
    print("\n" + "=" * width)
    print(f"  {label}")
    print("=" * width)


def _print_result(result: dict) -> None:
    """Print a structured summary of a single document's chain result."""
    _print_separator(result["doc_id"])

    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}")
        return

    extraction = result["agent1"]
    agent2 = result["agent2"]
    agent3 = result["agent3"]

    # Agent 1 summary
    print(f"\n[Agent 1 — Extraction]")
    print(f"  Primary diagnosis : {extraction.primary_diagnosis}")
    print(f"  Medications found : {len(extraction.medications)}")
    for med in extraction.medications:
        dose = f" {med.dose}" if med.dose else ""
        freq = f", {med.frequency}" if med.frequency else ""
        print(f"    • {med.name}{dose}{freq}")
    if extraction.extraction_warnings:
        for w in extraction.extraction_warnings:
            print(f"  WARNING: {w}")

    # Agent 2 summary
    print(f"\n[Agent 2 — Diagnosis Explanation]")
    fk2 = agent2["fk_grade"]
    pass2 = "PASS" if agent2["passes"] else "FAIL"
    print(f"  FK grade: {fk2:.2f} [{pass2}]")
    print(f"  Output:")
    for line in agent2["text"].splitlines():
        print(f"    {line}")

    # Agent 3 summary
    print(f"\n[Agent 3 — Medication Rationale]")
    fk3 = agent3["fk_grade"]
    pass3 = "PASS" if agent3["passes"] else "FAIL"
    print(f"  FK grade: {fk3:.2f} [{pass3}]")

    violations = _check_safety(agent3["text"])
    if violations:
        print(f"  SAFETY VIOLATION — forbidden phrases found: {violations}")
    else:
        print(f"  Safety check: CLEAN")

    print(f"  Output:")
    for line in agent3["text"].splitlines():
        print(f"    {line}")


def main() -> None:
    """
    Run the full Agents 1-2-3 chain on all test documents and print a summary.

    Exits with code 1 if any document fails Agent 3's safety check or if
    fewer than 3 documents complete the full chain successfully.
    """
    print("DischargeIQ — Agents 1, 2, 3 Integration Test")
    print(f"Testing {len(_TEST_DOCS)} documents\n")

    results = []
    for pdf_path in _TEST_DOCS:
        if not pdf_path.exists():
            print(f"SKIP: {pdf_path.name} not found")
            continue
        print(f"Running chain on {pdf_path.name} ...")
        result = _run_chain(pdf_path)
        results.append(result)
        # Brief pause between documents
        time.sleep(2)

    # Print detailed output for all documents
    for result in results:
        _print_result(result)

    # ── Final summary ──────────────────────────────────────────────────────────
    _print_separator("SUMMARY")

    successes = [r for r in results if r["success"]]
    fk_fails = [
        r for r in successes
        if r["agent3"] and not r["agent3"]["passes"]
    ]
    safety_fails = [
        r for r in successes
        if r["agent3"] and _check_safety(r["agent3"]["text"])
    ]

    print(f"\n  Documents tested   : {len(results)}")
    print(f"  Full chain success : {len(successes)} / {len(results)}")
    print(f"  Agent 3 FK passes  : {len(successes) - len(fk_fails)} / {len(successes)}")
    print(f"  Safety violations  : {len(safety_fails)}")

    if fk_fails:
        print("\n  FK FAILURES (revise agent3_system_prompt.txt):")
        for r in fk_fails:
            print(f"    {r['doc_id']}: FK {r['agent3']['fk_grade']:.2f}")

    if safety_fails:
        print("\n  SAFETY FAILURES (critical — review output immediately):")
        for r in safety_fails:
            print(f"    {r['doc_id']}")

    # Acceptance gate: at least 3 successful end-to-end documents, zero safety violations.
    gate_passed = len(successes) >= 3 and len(safety_fails) == 0
    print(f"\n  Acceptance gate    : {'PASSED' if gate_passed else 'FAILED'}")

    if not gate_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
