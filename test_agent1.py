"""
Test harness for Agent 1 (DIS-5) — Extraction agent.

Runs Agent 1 on all synthetic PDFs in test-data/ (10 clean documents) plus
the 4 stress-test edge-case documents in test-data/stress-test/ and prints
per-file results and a final pass/fail count.

Pass criteria (all four must be met):
  1. run_extraction_agent() returns without raising an exception.
  2. primary_diagnosis is a non-empty string.
  3. At least one medication was extracted.
  4. At least one follow-up appointment was extracted.

Hard gate: 8/10 passes on the original clean PDFs required before Agent 2
development starts. Stress-test results are reported separately.

Rate limiting:
  A short delay is inserted between API calls to stay within free-tier RPM
  limits. Most providers cap at 5–15 RPM; 15s gives comfortable headroom.

Usage:
    python test_agent1.py

Requires the API key for the chosen LLM_PROVIDER in the environment (or in a .env file
at project root). Default provider is openrouter, which needs OPENROUTER_API_KEY.
"""

import os
import sys
import time
from pathlib import Path

# Add the project root to sys.path so 'dischargeiq' is importable when running
# this script directly from the project root without installing the package.
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()  # Load .env from project root if present

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent

# Clean synthetic PDFs (original 10 documents, hard-gate set).
_TEST_DATA_DIR = Path(__file__).parent / "test-data"

# Edge-case stress-test PDFs (4 documents: prose, table, abbreviation, OCR).
_STRESS_DATA_DIR = Path(__file__).parent / "test-data" / "stress-test"

# Minimum passing documents from the original 10 to clear the hard gate.
_HARD_GATE_THRESHOLD = 8

# Seconds to wait between API calls to stay within free-tier RPM limits.
# Most free-tier providers cap at 5–15 RPM; 15s gives safe headroom.
# 10 calls = ~2.5 min total idle time.
_INTER_CALL_DELAY_SECONDS = 15


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

    provider = os.environ.get("LLM_PROVIDER", "openrouter")
    model_name = os.environ.get("LLM_MODEL", "default for provider")
    total = len(clean_files) + len(stress_files)
    print(f"Agent 1 test — {total} documents total ({len(clean_files)} original + {len(stress_files)} stress-test)")
    print(f"Provider: {provider}  |  Model: {model_name}  (set LLM_PROVIDER / LLM_MODEL in .env to override)")
    print(f"Delay : {_INTER_CALL_DELAY_SECONDS}s between calls (free-tier RPM limit)")

    clean_results = _run_batch(clean_files, "ORIGINAL SYNTHETIC SET", global_index_start=0)
    stress_results = _run_batch(stress_files, "STRESS-TEST EDGE CASES", global_index_start=len(clean_files))

    _print_summary(clean_results, stress_results)


if __name__ == "__main__":
    main()
