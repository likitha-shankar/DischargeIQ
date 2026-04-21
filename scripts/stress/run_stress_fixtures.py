"""
Run the 6 stress-test fixtures through the full DischargeIQ pipeline and
print a pass/fail report.

Not part of the hallucination suite — standalone probe for fixtures 9–14.

Usage:
    python scripts/stress/run_stress_fixtures.py                  # all 6
    python scripts/stress/run_stress_fixtures.py --fixtures 9,14  # just these
"""

import argparse
import asyncio
import re
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

from dischargeiq.pipeline.orchestrator import run_pipeline  # noqa: E402

FIXTURES_DIR = _REPO_ROOT / "dischargeiq" / "tests" / "fixtures"

CASES = [
    {
        "label": "F9  Epic CHF",
        "file":  "fixture_09_epic_chf.pdf",
        "expected_active_meds": 5,
        "expected_discontinued": ["metformin"],
        "notes": "5 active + 1 stopped (Metformin)",
    },
    {
        "label": "F10 Cerner pneumonia",
        "file":  "fixture_10_cerner_pneumonia.pdf",
        "expected_active_meds": 5,
        "expected_discontinued": [],
        "notes": "5 meds; Azithromycin new, 4 continued",
    },
    {
        "label": "F11 Word knee",
        "file":  "fixture_11_word_knee.pdf",
        "expected_active_meds": 4,
        "expected_discontinued": [],
        "notes": "4 meds (Percocet, Aspirin, Celebrex, Colace)",
    },
    {
        "label": "F12 Two-col post-MI",
        "file":  "fixture_12_twocolumn_mi.pdf",
        "expected_active_meds": 6,
        "expected_discontinued": [],
        "notes": "6 meds in two-column layout",
    },
    {
        "label": "F13 Pediatric appy",
        "file":  "fixture_13_pediatric_appy.pdf",
        "expected_active_meds": 2,
        "expected_discontinued": [],
        "notes": "2 meds (Ibuprofen, Acetaminophen); patient=child",
    },
    {
        "label": "F14 Multi-page sepsis",
        "file":  "fixture_14_multipage_sepsis.pdf",
        "expected_active_meds": 5,
        "expected_discontinued": ["glipizide"],
        "notes": "5 discharge (2 changed, 2 new, 1 continued) + Glipizide DC",
    },
]


def _status_counts(meds: list[dict]) -> dict[str, int]:
    """Count each Medication.status across a list of meds."""
    counts: dict[str, int] = {}
    for m in meds:
        s = (m.get("status") or "").lower() or "null"
        counts[s] = counts.get(s, 0) + 1
    return counts


def _has_dc_named(meds: list[dict], name: str) -> bool:
    """True if any med in the list has status=discontinued and matches name."""
    needle = name.lower()
    return any(
        (m.get("status") or "").lower() == "discontinued"
        and needle in (m.get("name") or "").lower()
        for m in meds
    )


def _parse_fixture_filter() -> set[int] | None:
    """Parse --fixtures flag into a set of fixture numbers, or None for all."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=str,
        default=None,
        help="Comma-separated fixture numbers to run (e.g. '9,14'). "
             "Omit to run all 6.",
    )
    args = parser.parse_args()
    if not args.fixtures:
        return None
    return {int(tok) for tok in args.fixtures.split(",") if tok.strip()}


def _fixture_number(label: str) -> int | None:
    """Extract the fixture number from a CASES label like 'F9  Epic CHF'."""
    m = re.match(r"F(\d+)", label)
    return int(m.group(1)) if m else None


def main() -> None:
    wanted = _parse_fixture_filter()
    cases = (
        CASES if wanted is None
        else [c for c in CASES if _fixture_number(c["label"]) in wanted]
    )
    if not cases:
        print("No cases match the requested --fixtures filter.")
        return

    print(f"{'case':22s} {'status':9s} {'#meds':>6s} {'#red':>5s} "
          f"{'#appt':>6s} {'FK':>5s} {'#warn':>6s}  verdict")
    print("-" * 90)

    summary: list[tuple[str, str]] = []
    for case in cases:
        label = case["label"]
        path = FIXTURES_DIR / case["file"]
        try:
            r = asyncio.run(run_pipeline(str(path)))
        except Exception as exc:
            print(f"{label:22s} CRASH     — pipeline raised {type(exc).__name__}: {exc}")
            summary.append((label, "CRASH"))
            continue

        ext = r.extraction.model_dump()
        meds = ext.get("medications", []) or []
        status_counts = _status_counts(meds)
        active_count = sum(
            c for s, c in status_counts.items() if s != "discontinued"
        )
        red_flags = ext.get("red_flag_symptoms", []) or []
        appts = ext.get("follow_up_appointments", []) or []
        warnings = ext.get("extraction_warnings", []) or []
        fk_grade = r.fk_scores.get("agent2", {}).get("fk_grade", "—")

        med_ok = active_count == case["expected_active_meds"]
        dc_ok = all(
            _has_dc_named(meds, n) for n in case["expected_discontinued"]
        )
        no_crash = r.pipeline_status in ("complete", "partial")
        verdict = "PASS" if (no_crash and med_ok and dc_ok) else "FAIL"

        print(
            f"{label:22s} {r.pipeline_status:9s} "
            f"{active_count:>6d} {len(red_flags):>5d} "
            f"{len(appts):>6d} {str(fk_grade):>5s} "
            f"{len(warnings):>6d}  {verdict}"
        )
        if not med_ok or not dc_ok:
            med_names = [m.get("name") for m in meds]
            status_str = ", ".join(
                f"{s}={c}" for s, c in sorted(status_counts.items())
            )
            print(f"   expected {case['expected_active_meds']} active "
                  f"+ {case['expected_discontinued']} DC")
            print(f"   got     meds={med_names}  statuses[{status_str}]")
        if warnings:
            for w in warnings:
                print(f"   warn: {w}")
        summary.append((label, verdict))

    print("-" * 90)
    passed = sum(1 for _, v in summary if v == "PASS")
    print(f"  {passed}/{len(summary)} PASS")


if __name__ == "__main__":
    main()
