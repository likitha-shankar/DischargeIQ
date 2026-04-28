"""
File: tests/test_agent1.py
Owner: Likitha Shankar
Description: Agent 1 regression suite — pytest-discoverable slow tests that enforce the
  8/10 hard gate across the original synthetic PDFs, plus a stress-test batch. Also
  contains a standalone main() for manual runs with per-file progress output.
Key functions/classes: test_hard_gate_original_set, test_stress_batch, _evaluate_document
Edge cases handled:
  - Sleep between calls for provider rate limits; continues suite after individual failures.
  - Hard gate asserted via pytest.fail(), not just printed.
Dependencies: dischargeiq.agents.extraction_agent, pathlib, dotenv-loaded env
Called by: ``pytest -m slow tests/test_agent1.py`` or ``python tests/test_agent1.py``.
"""

import os
import sys
import time
from pathlib import Path

import pytest

# Repo root — package ``dischargeiq`` is importable when running this file directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent

# Clean synthetic PDFs (original 10 documents, hard-gate set).
_TEST_DATA_DIR = _REPO_ROOT / "test-data"

# Edge-case stress-test PDFs (4 documents: prose, table, abbreviation, OCR).
_STRESS_DATA_DIR = _REPO_ROOT / "test-data" / "stress-test"

# Minimum passing documents from the original 10 to clear the hard gate.
_HARD_GATE_THRESHOLD = 8

# Seconds to wait between API calls to stay within Anthropic free-tier limits.
# Binding constraint: 10,000 input tokens/min. Agent 1 sends ~5,300 tokens per
# call (4,700-token system prompt + ~600-token PDF text). At 35 s gaps:
# 60/35 ≈ 1.7 calls/min × 5,300 = 9,010 tokens/min — safely under the limit.
_INTER_CALL_DELAY_SECONDS = 35


def _evaluate_document(pdf_path: Path) -> dict:
    """
    Run Agent 1 on a single PDF and return a structured result dict.

    Args:
        pdf_path: Path to the PDF file to evaluate.

    Returns:
        dict with keys:
            filename (str): Just the file name, not the full path.
            passed (bool): True if all pass criteria were met.
            primary_diagnosis (str): Extracted value, or error message.
            medication_count (int): Number of medications extracted.
            followup_count (int): Number of follow-up appointments extracted.
            warnings (list[str]): extraction_warnings from the model output.
            error (str | None): Exception message if extraction failed, else None.
    """
    result = {
        "filename": pdf_path.name,
        "passed": False,
        "primary_diagnosis": "",
        "medication_count": 0,
        "followup_count": 0,
        "warnings": [],
        "error": None,
    }

    try:
        pdf_text = extract_text_from_pdf(str(pdf_path))
        extraction = run_extraction_agent(pdf_text)

        result["primary_diagnosis"] = extraction.primary_diagnosis or ""
        result["medication_count"] = len(extraction.medications)
        result["followup_count"] = len(extraction.follow_up_appointments)
        result["warnings"] = extraction.extraction_warnings

        # All four pass criteria must hold.
        has_diagnosis = bool(result["primary_diagnosis"].strip())
        has_medications = result["medication_count"] > 0
        has_followups = result["followup_count"] > 0
        result["passed"] = has_diagnosis and has_medications and has_followups

    except (FileNotFoundError, OSError) as exc:
        result["error"] = f"PDF read error: {exc}"
    except ValueError as exc:
        # Covers json.JSONDecodeError (subclass of ValueError) and similar.
        result["error"] = f"Parse error: {exc}"
    except Exception as exc:  # noqa: BLE001 — catch-all for API and validation errors
        result["error"] = f"Unexpected error: {type(exc).__name__}: {exc}"

    return result


def _print_result(result: dict) -> None:
    """
    Print a formatted single-document result row to stdout.

    Args:
        result: Dict returned by _evaluate_document().
    """
    status_label = "PASS" if result["passed"] else "FAIL"
    print(f"\n{'=' * 60}")
    print(f"  File     : {result['filename']}")
    print(f"  Status   : {status_label}")
    print(f"  Diagnosis: {result['primary_diagnosis'] or '(none)'}")
    print(f"  Meds     : {result['medication_count']}")
    print(f"  Follow-up: {result['followup_count']}")

    if result["warnings"]:
        for warning in result["warnings"]:
            print(f"  Warning  : {warning}")

    if result["error"]:
        print(f"  Error    : {result['error']}")


def _print_summary(clean_results: list[dict], stress_results: list[dict]) -> None:
    """
    Print the final pass/fail counts and hard-gate verdict.

    Reports the original 10-document set and the 4 stress-test documents
    separately so the hard-gate verdict is not diluted by edge-case failures.

    Args:
        clean_results: Results for the original 10 synthetic PDFs.
        stress_results: Results for the 4 stress-test edge-case PDFs.
    """
    clean_pass = sum(1 for r in clean_results if r["passed"])
    stress_pass = sum(1 for r in stress_results if r["passed"])
    total_pass = clean_pass + stress_pass
    total = len(clean_results) + len(stress_results)

    print(f"\n{'=' * 60}")
    print(f"  ORIGINAL SET : {clean_pass}/{len(clean_results)} passed")
    print(f"  STRESS-TEST  : {stress_pass}/{len(stress_results)} passed")
    print(f"  TOTAL        : {total_pass}/{total} passed")
    print()

    if clean_pass >= _HARD_GATE_THRESHOLD:
        print(f"  HARD GATE: CLEARED ({clean_pass}/{len(clean_results)} >= {_HARD_GATE_THRESHOLD})")
        print("  Agent 2 development may begin.")
    else:
        print(f"  HARD GATE: NOT CLEARED ({clean_pass}/{len(clean_results)} < {_HARD_GATE_THRESHOLD})")
        print("  Fix Agent 1 before starting Agent 2.")
    print(f"{'=' * 60}\n")


def _run_batch(pdf_files: list[Path], label: str, global_index_start: int) -> list[dict]:
    """
    Run Agent 1 on a list of PDF files with inter-call rate limiting.

    Args:
        pdf_files: Ordered list of PDF paths to process.
        label: Section header to print before the batch (e.g. "ORIGINAL SET").
        global_index_start: Used to determine whether to sleep before the very
            first call in the batch (skip sleep only for index 0 of the entire
            run, not just this batch).

    Returns:
        list[dict]: One result dict per PDF, in the same order as pdf_files.
    """
    print(f"\n--- {label} ({len(pdf_files)} documents) ---")
    results = []
    for local_index, pdf_path in enumerate(pdf_files):
        # Always sleep between calls — the first call of a later batch must
        # also respect the rate limit relative to the last call of the prior batch.
        if global_index_start + local_index > 0:
            time.sleep(_INTER_CALL_DELAY_SECONDS)

        print(f"\nProcessing: {pdf_path.name} ...", end="", flush=True)
        result = _evaluate_document(pdf_path)
        results.append(result)
        _print_result(result)
    return results


def main() -> None:
    """
    Entry point: run Agent 1 on all original PDFs and all stress-test PDFs,
    then print per-file results and a combined final summary.
    """
    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    stress_files = sorted(_STRESS_DATA_DIR.glob("messy_*.pdf"))

    if not clean_files:
        print(f"No PDFs found in {_TEST_DATA_DIR}. Aborting.")
        sys.exit(1)

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    total = len(clean_files) + len(stress_files)
    print(f"Agent 1 test — {total} documents total ({len(clean_files)} original + {len(stress_files)} stress-test)")
    print(f"Model : {model_name}  (set GEMINI_MODEL in .env to override)")
    print(f"Delay : {_INTER_CALL_DELAY_SECONDS}s between calls (free-tier RPM limit)")

    clean_results = _run_batch(clean_files, "ORIGINAL SYNTHETIC SET", global_index_start=0)
    stress_results = _run_batch(stress_files, "STRESS-TEST EDGE CASES", global_index_start=len(clean_files))

    _print_summary(clean_results, stress_results)


if __name__ == "__main__":
    main()


# ──────────────────────────────────────────────────────────────────────────────
# Pytest-discoverable tests
# Run: pytest -m slow tests/test_agent1.py
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_hard_gate_original_set() -> None:
    """
    Assert Agent 1 passes on at least 8/10 original synthetic PDFs.

    This is the hard gate that must clear before Agent 2 development begins.
    Failure exits non-zero so CI blocks automatically.

    Each PDF is evaluated for:
        - primary_diagnosis present and non-empty
        - at least one medication extracted
        - at least one follow-up appointment extracted
    """
    pdf_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    assert pdf_files, f"No PDFs found in {_TEST_DATA_DIR} — check test-data/ directory."

    results = []
    for index, pdf_path in enumerate(pdf_files):
        if index > 0:
            time.sleep(_INTER_CALL_DELAY_SECONDS)
        results.append(_evaluate_document(pdf_path))

    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]

    summary_lines = [f"Agent 1 hard gate: {len(passed)}/{len(results)} passed"]
    for r in failed:
        summary_lines.append(
            f"  FAIL {r['filename']}: diag={r['primary_diagnosis']!r} "
            f"meds={r['medication_count']} followups={r['followup_count']} "
            f"err={r['error']}"
        )

    assert len(passed) >= _HARD_GATE_THRESHOLD, (
        f"HARD GATE NOT CLEARED — {len(passed)}/{len(results)} passed "
        f"(need {_HARD_GATE_THRESHOLD}).\n" + "\n".join(summary_lines)
    )


@pytest.mark.slow
@pytest.mark.parametrize("pdf_path", sorted((_REPO_ROOT / "test-data").glob("*.pdf")))
def test_agent1_extracts_diagnosis(pdf_path: Path) -> None:
    """
    Assert Agent 1 extracts a non-empty primary_diagnosis for each PDF.

    Parametrized so each document appears as a separate test case in pytest
    output, making it easy to spot which specific file fails.

    Args:
        pdf_path: One PDF from test-data/, injected by parametrize.
    """
    result = _evaluate_document(pdf_path)
    assert result["primary_diagnosis"].strip(), (
        f"{pdf_path.name}: primary_diagnosis was empty or None. "
        f"Error: {result['error']}"
    )


@pytest.mark.slow
def test_stress_batch_no_crashes() -> None:
    """
    Assert Agent 1 does not crash on any stress-test PDF.

    Stress PDFs are edge-case documents (messy layout, tables, OCR-like).
    This test does not enforce a pass threshold — it only verifies the agent
    returns without an unhandled exception for every file.
    """
    stress_files = sorted(_STRESS_DATA_DIR.glob("messy_*.pdf"))
    if not stress_files:
        pytest.skip(f"No stress PDFs found in {_STRESS_DATA_DIR}")

    for index, pdf_path in enumerate(stress_files):
        if index > 0:
            time.sleep(_INTER_CALL_DELAY_SECONDS)
        result = _evaluate_document(pdf_path)
        assert result["error"] is None or "Parse error" in (result["error"] or ""), (
            f"{pdf_path.name}: Agent 1 crashed with unexpected error: {result['error']}"
        )
