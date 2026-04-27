"""
File: tests/test_agents_1_2.py
Owner: Deepesh Kumar
Description: Manual integration runner that walks PDFs under test-data/, runs
  extract_text_from_pdf + run_extraction_agent then run_diagnosis_agent, and prints
  per-file outcomes for Agent 1→2 debugging (not pytest-discovered by default).
Key functions/classes: run_tests
Edge cases handled:
  - Skips non-PDF files; continues on per-file failures while tallying results.
Dependencies: dischargeiq.agents.extraction_agent, dischargeiq.agents.diagnosis_agent, dotenv.
Called by: ``python tests/test_agents_1_2.py`` from repo root (or ``python -m tests.test_agents_1_2``).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(_REPO_ROOT / ".env")

from dischargeiq.agents.extraction_agent import run_extraction_agent, extract_text_from_pdf
from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent

TEST_DATA_DIR = _REPO_ROOT / "test-data"


def run_tests():
    """
    Run Agents 1 and 2 end-to-end on all PDFs in test-data/.

    Prints results per document and confirms the Agent 2 FK gate:
    all outputs must pass FK grade <= 6.0.
    """
    print("=" * 65)
    print("DischargeIQ — Agents 1 + 2 Integration Test")
    print("=" * 65)

    # Collect all PDFs — skip stress-test folder
    pdf_files = sorted([
        f for f in TEST_DATA_DIR.glob("*.pdf")
    ])

    if not pdf_files:
        print(f"\n[FAIL] No PDFs found in {TEST_DATA_DIR}")
        print("   Generate synthetic test documents first (see project docs).")
        return

    results = []

    for pdf_path in pdf_files:
        doc_id = pdf_path.name
        print(f"\n[PDF] {doc_id}")

        # ── Agent 1 ────────────────────────────────────────────────────────────
        try:
            pdf_text = extract_text_from_pdf(str(pdf_path))
            extraction = run_extraction_agent(pdf_text)
            print(f"   Agent 1 OK  diagnosis: {extraction.primary_diagnosis}")
        except Exception as e:
            print(f"   Agent 1 FAIL  FAILED: {e}")
            results.append({"doc": doc_id, "status": "A1_ERROR", "fk_grade": None})
            continue

        # ── Agent 2 ────────────────────────────────────────────────────────────
        try:
            output = run_diagnosis_agent(extraction, document_id=doc_id)
            status = "PASS" if output["passes"] else "FK_FAIL"
            print(f"   Agent 2 {'OK' if output['passes'] else 'WARN'}  FK grade: {output['fk_grade']} -- {status}")
            print(f"   Output: {output['text'][:120]}...")
            results.append({"doc": doc_id, "status": status, "fk_grade": output["fk_grade"]})
        except Exception as e:
            print(f"   Agent 2 FAIL  FAILED: {e}")
            results.append({"doc": doc_id, "status": "A2_ERROR", "fk_grade": None})

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("RESULTS SUMMARY")
    print("=" * 65)

    pass_count  = sum(1 for r in results if r["status"] == "PASS")
    fail_count  = sum(1 for r in results if r["status"] == "FK_FAIL")
    error_count = sum(1 for r in results if "ERROR" in r["status"])
    total = len(results)

    for r in results:
        icon = "[OK]  " if r["status"] == "PASS" else ("[WARN]" if r["status"] == "FK_FAIL" else "[FAIL]")
        fk = f"FK {r['fk_grade']:.2f}" if r["fk_grade"] is not None else "N/A"
        print(f"  {icon}  {r['doc']:<40} {r['status']:<12} {fk}")

    print(f"\nTotal documents: {total}")
    print(f"FK passed:       {pass_count}")
    if fail_count:
        print(f"FK failed:       {fail_count} — revise prompts/agent2_system_prompt.txt")
    if error_count:
        print(f"Errors:          {error_count} — check API keys and model names")

    print("\nFK scores logged to: dischargeiq/evaluation/fk_log.csv")
    print("\n[NOTE] Per CLAUDE.md: do NOT git commit from here.")
    print("    Review output above, then commit manually.")

    # Agent 2 FK gate check
    if pass_count == total and error_count == 0:
        print(f"\n[OK] AGENT 2 FK GATE MET: All {total} outputs pass FK <= 6.0")
        print("   Agent 2 outputs meet the FK threshold; downstream agents can proceed.")
    else:
        not_passing = total - pass_count
        print(f"\n[FAIL] AGENT 2 FK GATE NOT MET: {not_passing} output(s) not passing.")
        print("   Fix issues above before opening the PR.")


if __name__ == "__main__":
    run_tests()
