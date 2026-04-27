"""
File: scripts/manual/test_er_compatibility.py
Owner: Likitha Shankar
Description: Manual compatibility script for ER-style discharge PDFs.
  Runs the full DischargeIQ pipeline on er_laceration_01.pdf and
  er_asthma_01.pdf, prints each agent's text output and the Agent 6
  gap score, and flags any agent that returned empty output or caused
  a partial pipeline status.

  This is a manual diagnostic script -- it calls the real LLM and requires
  ANTHROPIC_API_KEY (or your configured LLM_PROVIDER) to be set in .env.

Usage (from repo root):
    python scripts/manual/test_er_compatibility.py

Flags any agent whose output is empty or whose pipeline_status is "partial".
Exits with code 1 if any doc triggers a partial or agent failure.
Dependencies:
    - dischargeiq.pipeline.orchestrator.run_pipeline (full async pipeline)
    - .env keys for LLM_PROVIDER
"""

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_REPO_ROOT / ".env")

from dischargeiq.pipeline.orchestrator import run_pipeline

_ER_PDFS = [
    _REPO_ROOT / "test-data" / "er_laceration_01.pdf",
    _REPO_ROOT / "test-data" / "er_asthma_01.pdf",
]

_AGENT_FIELDS = [
    ("diagnosis_explanation", "Agent 2 — Diagnosis Explanation"),
    ("medication_rationale",  "Agent 3 — Medication Rationale"),
    ("recovery_trajectory",   "Agent 4 — Recovery Trajectory"),
    ("escalation_guide",      "Agent 5 — Escalation Guide"),
]


def _divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def _section(label: str, text: str) -> None:
    print(f"\n--- {label} ---")
    if text and text.strip():
        print(text.strip()[:800] + ("…" if len(text) > 800 else ""))
    else:
        print("[EMPTY — agent returned no output]")


async def _run_and_report(pdf_path: Path) -> bool:
    """Run full pipeline on one PDF and print results. Returns True if OK."""
    _divider(f"PDF: {pdf_path.name}")

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        print("Run: python test-data/generate_er_pdfs.py")
        return False

    print(f"Running pipeline on {pdf_path.name}…")
    result = await run_pipeline(str(pdf_path))

    print(f"\nPipeline status : {result.pipeline_status}")
    print(f"Primary diagnosis: {result.extraction.primary_diagnosis}")
    print(f"Medications      : {len(result.extraction.medications)}")
    print(f"Follow-ups       : {len(result.extraction.follow_up_appointments)}")
    print(f"Warnings         : {len(result.extraction.red_flag_symptoms)}")

    all_ok = True

    for field_key, label in _AGENT_FIELDS:
        text = getattr(result, field_key, "") or ""
        _section(label, text)
        if not text.strip():
            print(f"[FLAG] {label} is EMPTY")
            all_ok = False

    # Agent 6
    sim = result.patient_simulator
    print(f"\n--- Agent 6 - AI Patient Simulator ---")
    if sim:
        print(f"Gap score      : {sim.overall_gap_score}/10")
        print(f"Total concepts : {len(sim.missed_concepts)}")
        unanswered = [c for c in sim.missed_concepts if not c.answered_by_doc]
        critical   = [c for c in unanswered if c.severity == "critical"]
        moderate   = [c for c in unanswered if c.severity == "moderate"]
        print(f"Unanswered     : {len(unanswered)} ({len(critical)} critical, {len(moderate)} moderate)")
        print(f"Summary        : {sim.simulator_summary[:300]}")
        print("\nCritical gaps:")
        for c in critical:
            print(f"  Q: {c.question}")
            print(f"     GAP: {c.gap_summary}")
    else:
        print("[EMPTY — Agent 6 returned no output or was skipped]")

    if result.pipeline_status == "partial":
        print(f"\n[FLAG] pipeline_status=partial for {pdf_path.name}")
        all_ok = False

    return all_ok


async def main() -> None:
    all_passed = True
    for pdf_path in _ER_PDFS:
        ok = await _run_and_report(pdf_path)
        if not ok:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All ER compatibility checks passed.")
    else:
        print("One or more ER compatibility checks FAILED — see above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
