"""
test_agents_1_2.py

Integration test for Agent 1 (Extraction) + Agent 2 (Diagnosis Explanation).
DIS-8 acceptance criteria: confirms Agents 1 and 2 running end-to-end
on multiple documents with FK scores logged.

Usage:
    python test_agents_1_2.py

Requirements:
    - ANTHROPIC_API_KEY set in .env
    - GOOGLE_STUDIO_API_KEY set in .env (for Agent 1 / Gemini)
    - test-data/ directory with synthetic discharge PDFs from DIS-3

Per CLAUDE.md: do NOT run git commit, push, or add from this script.
Review the output, then the human commits manually.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent))

from dischargeiq.agents.extraction_agent import run_extraction_agent, extract_text_from_pdf
from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent

TEST_DATA_DIR = Path(__file__).parent / "test-data"


def run_tests():
    """
    Run Agents 1 and 2 end-to-end on all PDFs in test-data/.

    Prints results per document and confirms the DIS-8 gate:
    all outputs must pass FK grade <= 6.0.
    """
    print("=" * 65)
    print("DischargeIQ — Agents 1 + 2 Integration Test (DIS-8)")
    print("=" * 65)

    # Collect all PDFs — skip stress-test folder
    pdf_files = sorted([
        f for f in TEST_DATA_DIR.glob("*.pdf")
    ])

    if not pdf_files:
        print(f"\n[FAIL] No PDFs found in {TEST_DATA_DIR}")
        print("   Run DIS-3 to generate synthetic test documents first.")
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

    # DIS-8 gate check
    if pass_count == total and error_count == 0:
        print(f"\n[OK] DIS-8 GATE MET: All {total} outputs pass FK <= 6.0")
        print("   Post in group chat: DIS-8 done — Agent 2 ready. @Suchithra DIS-9 is unblocked.")
    else:
        not_passing = total - pass_count
        print(f"\n[FAIL] DIS-8 GATE NOT MET: {not_passing} output(s) not passing.")
        print("   Fix issues above before opening the PR.")


if __name__ == "__main__":
    run_tests()
