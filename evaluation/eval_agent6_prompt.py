"""
File: evaluation/eval_agent6_prompt.py
Owner: Likitha Shankar
Description: Eval script for Agent 6 system prompt quality.
  Runs the live Agent 6 against all 10 synthetic PDFs in test-data/,
  prints per-doc gap scores and concept counts, and saves a CSV summary
  to evaluation/agent6_eval_results.csv.

  This is an eval script, NOT a unit test — it calls the real LLM and
  requires ANTHROPIC_API_KEY (or your configured LLM_PROVIDER) to be set
  in .env. Do not run this in CI or with mocks.

Usage (from repo root):
    python evaluation/eval_agent6_prompt.py

Output:
    - Prints a table of per-doc results to stdout
    - Writes evaluation/agent6_eval_results.csv
    - Exits with code 1 if any doc returns a partial/failed result

Dependencies:
    - dischargeiq.agents.extraction_agent (Agent 1 — extracts PDF text)
    - dischargeiq.agents.patient_simulator_agent (Agent 6)
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq.models.pipeline.PatientSimulatorOutput
    - All LLM provider config from .env (LLM_PROVIDER, LLM_MODEL, API keys)
"""

import csv
import os
import sys
import time
from pathlib import Path

# Ensure the repo root is on the path so dischargeiq imports resolve
# regardless of where the script is invoked from.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(dotenv_path=_REPO_ROOT / ".env")

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.agents.patient_simulator_agent import run_patient_simulator_agent

# ── Configuration ──────────────────────────────────────────────────────────────

_TEST_DATA_DIR = _REPO_ROOT / "test-data"
_OUTPUT_CSV    = _REPO_ROOT / "evaluation" / "agent6_eval_results.csv"
_CSV_FIELDS    = [
    "pdf_file",
    "gap_score",
    "total_concepts",
    "unanswered_concepts",
    "critical_gaps",
    "moderate_gaps",
    "minor_gaps",
    "fk_grade",
    "passes_fk",
    "simulator_summary",
    "status",
    "elapsed_s",
]

# ── Helpers ────────────────────────────────────────────────────────────────────


def _collect_pdfs() -> list[Path]:
    """Return sorted list of PDF paths in test-data/ (top level only)."""
    pdfs = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"[ERROR] No PDFs found in {_TEST_DATA_DIR}. "
              f"Run test-data generation scripts first.", file=sys.stderr)
        sys.exit(1)
    return pdfs


def _run_one(pdf_path: Path) -> dict:
    """
    Run Agent 1 extraction then Agent 6 simulation on one PDF.

    Returns a result dict matching _CSV_FIELDS.
    Never raises — failures are captured in the 'status' field.
    """
    start = time.monotonic()
    result: dict = {
        "pdf_file":           pdf_path.name,
        "gap_score":          0,
        "total_concepts":     0,
        "unanswered_concepts":0,
        "critical_gaps":      0,
        "moderate_gaps":      0,
        "minor_gaps":         0,
        "fk_grade":           0.0,
        "passes_fk":          False,
        "simulator_summary":  "",
        "status":             "ok",
        "elapsed_s":          0.0,
    }

    try:
        pdf_text  = extract_text_from_pdf(str(pdf_path))
        extraction = run_extraction_agent(pdf_text)
    except Exception as exc:
        result["status"] = f"agent1_error: {exc}"
        result["elapsed_s"] = round(time.monotonic() - start, 2)
        return result

    try:
        sim = run_patient_simulator_agent(extraction, pdf_path.name)
    except Exception as exc:
        result["status"] = f"agent6_error: {exc}"
        result["elapsed_s"] = round(time.monotonic() - start, 2)
        return result

    concepts   = sim.missed_concepts or []
    unanswered = [c for c in concepts if not c.answered_by_doc]

    result.update({
        "gap_score":           sim.overall_gap_score,
        "total_concepts":      len(concepts),
        "unanswered_concepts": len(unanswered),
        "critical_gaps":       sum(1 for c in unanswered if c.severity == "critical"),
        "moderate_gaps":       sum(1 for c in unanswered if c.severity == "moderate"),
        "minor_gaps":          sum(1 for c in unanswered if c.severity == "minor"),
        "fk_grade":            sim.fk_grade,
        "passes_fk":           sim.passes,
        "simulator_summary":   sim.simulator_summary[:200],
        "status":              "ok",
        "elapsed_s":           round(time.monotonic() - start, 2),
    })
    return result


def _print_table(results: list[dict]) -> None:
    """Print a formatted summary table to stdout."""
    header = (
        f"{'PDF':<30} {'GAP':>4} {'TOTAL':>6} {'UNANS':>6} "
        f"{'CRIT':>5} {'MOD':>4} {'MIN':>4} {'FK':>5} {'STATUS'}"
    )
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))
    for r in results:
        name = r["pdf_file"][:29]
        print(
            f"{name:<30} {r['gap_score']:>4} {r['total_concepts']:>6} "
            f"{r['unanswered_concepts']:>6} {r['critical_gaps']:>5} "
            f"{r['moderate_gaps']:>4} {r['minor_gaps']:>4} "
            f"{r['fk_grade']:>5.1f} {r['status']}"
        )
    print("=" * len(header))

    total_docs   = len(results)
    ok_docs      = sum(1 for r in results if r["status"] == "ok")
    avg_gap      = (
        sum(r["gap_score"] for r in results if r["status"] == "ok") / ok_docs
        if ok_docs else 0
    )
    total_crit   = sum(r["critical_gaps"] for r in results if r["status"] == "ok")
    print(
        f"\nSummary: {ok_docs}/{total_docs} docs succeeded | "
        f"avg gap score {avg_gap:.1f} | total critical gaps {total_crit}"
    )


def _write_csv(results: list[dict]) -> None:
    """Write results to evaluation/agent6_eval_results.csv."""
    _OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved → {_OUTPUT_CSV}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    pdfs    = _collect_pdfs()
    results = []

    print(f"Running Agent 6 eval on {len(pdfs)} PDFs in {_TEST_DATA_DIR}…\n")

    for pdf_path in pdfs:
        print(f"  Processing {pdf_path.name}…", end=" ", flush=True)
        result = _run_one(pdf_path)
        results.append(result)
        status_tag = "OK" if result["status"] == "ok" else "FAIL"
        print(
            f"[{status_tag}] gap={result['gap_score']} "
            f"crit={result['critical_gaps']} elapsed={result['elapsed_s']}s"
        )

    _print_table(results)
    _write_csv(results)

    failed = [r for r in results if r["status"] != "ok"]
    if failed:
        print(f"\n[WARN] {len(failed)} doc(s) failed — check status column in CSV.",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
