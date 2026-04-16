"""
Prompt verification test for Agent 1 (DIS-5) — post-prompt-fix regression suite.

Covers five verification areas:
  Test A — Targeted regression on 4 known-failure PDFs
  Test B — Medication status field validity across all 10 original PDFs
  Test C — Follow-up provider field contamination check
  Test D — False extraction-warning rate on clean PDFs
  Test E — Procedures completeness (pdfplumber count vs Agent 1 count)

Does NOT modify any agent code or prompt files.
Only reads:
  dischargeiq/agents/extraction_agent.py
  dischargeiq/prompts/agent1_system_prompt.txt  (already updated)

Run:
    python test_agent1_prompt_verification.py

Requires LLM_PROVIDER key in .env (default: ollama with qwen2.5:7b).
Uses a 10-second inter-call delay as instructed.
"""

import sys
import time
from pathlib import Path
from typing import Optional

import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.models.extraction import ExtractionOutput

# ── Constants ─────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent
_TEST_DATA_DIR = _ROOT / "test-data"

_INTER_CALL_DELAY = 10  # seconds between LLM calls

# Exact set of allowed medication status values per the locked schema.
_VALID_STATUSES = {"new", "changed", "continued", "discontinued", None}

# Words that indicate a clinic/facility rather than a named clinician.
_FACILITY_WORDS = {
    "clinic", "center", "centre", "therapy", "health", "department",
    "unit", "service", "hospital", "program", "programme", "outpatient",
    "inpatient", "home", "rehabilitation", "rehab",
}

# PDFs for Test A regression check.
_REGRESSION_PDFS = [
    "heart_failure_01.pdf",
    "hip_replacement_02.pdf",
    "copd_01.pdf",
    "hip_replacement_01.pdf",
]

# Expected outcomes for Test A (None means "no specific expectation beyond no crash").
_REGRESSION_EXPECTED = {
    "heart_failure_01.pdf": {
        "furosemide_status": "changed",
        "third_followup_provider": None,
        "third_followup_specialty_contains": "Nutritionist",
    },
    "hip_replacement_02.pdf": {
        "tramadol_status_not": "discontinued",
        "no_false_abbrev_warning": True,
    },
    "copd_01.pdf": {},       # no regressions expected
    "hip_replacement_01.pdf": {},  # no regressions expected
}


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _run(pdf_path: Path) -> tuple[Optional[ExtractionOutput], Optional[Exception]]:
    """Run Agent 1 on a single PDF. Never raises — returns (result, error)."""
    try:
        text = extract_text_from_pdf(str(pdf_path))
        return run_extraction_agent(text), None
    except Exception as exc:  # noqa: BLE001
        return None, exc


def _hr(width: int = 72) -> None:
    print("─" * width)


def _count_procedure_bullets(pdf_path: Path) -> int:
    """
    Count procedure lines in the raw PDF text by looking for a PROCEDURES
    PERFORMED section and counting non-empty lines that follow it until the
    next section header (all-caps line or blank separator).

    Returns 0 if no such section is found.
    """
    with pdfplumber.open(str(pdf_path)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    lines = full_text.splitlines()
    in_section = False
    count = 0
    for line in lines:
        stripped = line.strip()
        # Detect section header for procedures.
        if any(kw in stripped.upper() for kw in ("PROCEDURES PERFORMED", "PROCEDURES:")):
            in_section = True
            continue
        # Stop at the next major section header (all-caps non-empty line
        # that doesn't start with a bullet or dash).
        if in_section:
            if stripped and stripped == stripped.upper() and not stripped.startswith(("-", "•", "*")):
                break
            if stripped.startswith(("-", "•", "*")) or (stripped and not stripped[0].isspace()):
                if stripped:
                    count += 1
    return count


# ── Test A ─────────────────────────────────────────────────────────────────────

def _check_heart_failure_01(result: ExtractionOutput) -> list[str]:
    """Return list of failure reasons for heart_failure_01."""
    failures = []

    # Furosemide must be "changed" (IV inpatient -> oral discharge).
    furosemide = next(
        (m for m in result.medications if "furosemide" in m.name.lower()), None
    )
    if furosemide is None:
        failures.append("Furosemide not found in medications")
    elif furosemide.status != "changed":
        failures.append(
            f"Furosemide status = {furosemide.status!r}, expected 'changed'"
        )

    # Third follow-up must have provider=null and specialty containing "Nutritionist".
    if len(result.follow_up_appointments) >= 3:
        third = result.follow_up_appointments[2]
        if third.provider is not None:
            failures.append(
                f"Third follow-up provider = {third.provider!r}, expected null"
            )
        if third.specialty is None or "nutritionist" not in third.specialty.lower():
            failures.append(
                f"Third follow-up specialty = {third.specialty!r}, expected 'Nutritionist'"
            )
    else:
        failures.append(
            f"Only {len(result.follow_up_appointments)} follow-ups extracted, expected ≥3"
        )

    return failures


def _check_hip_replacement_02(result: ExtractionOutput) -> list[str]:
    """Return list of failure reasons for hip_replacement_02."""
    failures = []

    # Tramadol must NOT be "discontinued" (it is in the discharge meds list).
    tramadol = next(
        (m for m in result.medications if "tramadol" in m.name.lower()), None
    )
    if tramadol is not None and tramadol.status == "discontinued":
        failures.append(
            "Tramadol status = 'discontinued' — must not be discontinued "
            "if listed in discharge medications"
        )

    # Must not fire false abbreviation warning on this clean document.
    abbrev_warning = "Document uses abbreviated clinical shorthand"
    if any(abbrev_warning in w for w in result.extraction_warnings):
        failures.append("False abbreviation warning fired on clean document")

    return failures


def run_test_a() -> dict:
    """
    Test A: Targeted regression on 4 known-failure PDFs.

    Returns dict with pass_count and per-pdf details.
    """
    print("\n" + "═" * 72)
    print("  TEST A — Targeted Regression (4 PDFs)")
    print("═" * 72)

    details = []
    first_call = True

    for filename in _REGRESSION_PDFS:
        if not first_call:
            time.sleep(_INTER_CALL_DELAY)
        first_call = False

        pdf_path = _TEST_DATA_DIR / filename
        print(f"\n  [{filename}]")
        result, error = _run(pdf_path)

        if error or result is None:
            print(f"  ERROR: {type(error).__name__}: {error}")
            details.append({"filename": filename, "passed": False,
                            "failures": [str(error)]})
            continue

        # Print medications.
        print("  Medications:")
        for med in result.medications:
            print(f"    {med.name:<30} status={med.status!r}")

        # Print follow-ups.
        print("  Follow-ups:")
        for fu in result.follow_up_appointments:
            print(f"    provider={fu.provider!r:<30} specialty={fu.specialty!r}")

        # Print warnings.
        print(f"  Warnings: {result.extraction_warnings or '(none)'}")

        # Check expected outcomes.
        failures: list[str] = []
        if filename == "heart_failure_01.pdf":
            failures = _check_heart_failure_01(result)
        elif filename == "hip_replacement_02.pdf":
            failures = _check_hip_replacement_02(result)
        # copd_01 and hip_replacement_01: just verify no crash and diagnosis present.
        elif not result.primary_diagnosis:
            failures.append("primary_diagnosis is empty")

        passed = len(failures) == 0
        label = "PASS" if passed else "FAIL"
        print(f"  → {label}", end="")
        if failures:
            for f in failures:
                print(f"\n    ✗ {f}", end="")
        print()
        details.append({"filename": filename, "passed": passed, "failures": failures})

    pass_count = sum(1 for d in details if d["passed"])
    _hr()
    print(f"  Test A: {pass_count}/{len(details)} passed\n")
    return {"pass_count": pass_count, "total": len(details), "details": details}


# ── Test B ─────────────────────────────────────────────────────────────────────

def run_test_b() -> dict:
    """
    Test B: Medication status validity across all 10 original PDFs.

    Flags any status not in {new, changed, continued, discontinued, null}
    and any medication in a discharge section with status='discontinued'.
    """
    print("\n" + "═" * 72)
    print("  TEST B — Medication Status Field Validity (10 PDFs)")
    print("═" * 72)

    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    issues: list[str] = []
    first_call = True

    print(f"\n  {'PDF':<28} {'Medication':<28} {'Status':<16} Valid?")
    _hr()

    for pdf_path in clean_files:
        if not first_call:
            time.sleep(_INTER_CALL_DELAY)
        first_call = False

        result, error = _run(pdf_path)
        if error or result is None:
            print(f"  {pdf_path.name:<28} ERROR: {type(error).__name__}")
            issues.append(f"{pdf_path.name}: agent error — {error}")
            continue

        for med in result.medications:
            valid = med.status in _VALID_STATUSES
            valid_label = "OK" if valid else "⚠ INVALID"

            # Flag discontinued on a discharge-listed med (heuristic: all meds
            # returned by Agent 1 are from the discharge list unless noted otherwise).
            disc_flag = ""
            if med.status == "discontinued":
                valid_label = "⚠ DISCONTINUED in discharge list"
                issues.append(
                    f"{pdf_path.name}: {med.name} has status='discontinued' "
                    f"— should not appear in discharge medication list"
                )

            if not valid and not disc_flag:
                issues.append(
                    f"{pdf_path.name}: {med.name} has invalid status={med.status!r}"
                )

            status_str = repr(med.status)
            print(
                f"  {pdf_path.name:<28} {med.name:<28} {status_str:<16} {valid_label}"
            )

    _hr()
    issue_count = len(issues)
    if issue_count == 0:
        print(f"  Test B: 0 issues found ✓\n")
    else:
        print(f"  Test B: {issue_count} issue(s) found")
        for iss in issues:
            print(f"    ⚠ {iss}")
        print()
    return {"issue_count": issue_count, "issues": issues}


# ── Test C ─────────────────────────────────────────────────────────────────────

def _provider_contaminated(provider: Optional[str]) -> Optional[str]:
    """
    Return a description of the contamination if provider looks wrong, else None.

    Checks:
    - Contains "/" or "—" (likely combined field)
    - Contains a facility word (clinic, therapy, health, etc.)
    """
    if provider is None:
        return None
    lower = provider.lower()
    if "/" in provider or "—" in provider or " - " in provider:
        return f"contains separator character: {provider!r}"
    for word in _FACILITY_WORDS:
        if word in lower.split():
            return f"contains facility word '{word}': {provider!r}"
    return None


def _specialty_missing_discipline(
    provider: Optional[str], specialty: Optional[str]
) -> Optional[str]:
    """
    Return a description if provider contains a clinical discipline but specialty is null.
    """
    if provider is None or specialty is not None:
        return None
    discipline_words = {
        "cardiology", "pulmonology", "orthopedic", "surgery", "therapy",
        "nutrition", "endocrinology", "nephrology", "neurology", "oncology",
    }
    lower = provider.lower()
    for word in discipline_words:
        if word in lower:
            return (
                f"provider={provider!r} contains discipline '{word}' "
                f"but specialty=null"
            )
    return None


def run_test_c() -> dict:
    """
    Test C: Follow-up provider field contamination check across 10 PDFs.
    """
    print("\n" + "═" * 72)
    print("  TEST C — Follow-up Provider Field Contamination (10 PDFs)")
    print("═" * 72)

    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    issues: list[str] = []
    first_call = True

    for pdf_path in clean_files:
        if not first_call:
            time.sleep(_INTER_CALL_DELAY)
        first_call = False

        result, error = _run(pdf_path)
        if error or result is None:
            issues.append(f"{pdf_path.name}: agent error — {error}")
            continue

        print(f"\n  [{pdf_path.name}]")
        for idx, fu in enumerate(result.follow_up_appointments):
            flag = (
                _provider_contaminated(fu.provider)
                or _specialty_missing_discipline(fu.provider, fu.specialty)
            )
            marker = "⚠" if flag else "✓"
            print(
                f"  {marker} [{idx+1}] provider={fu.provider!r:<32} "
                f"specialty={fu.specialty!r}"
            )
            if flag:
                issues.append(f"{pdf_path.name} follow-up [{idx+1}]: {flag}")

    _hr()
    if not issues:
        print(f"\n  Test C: 0 contamination issues found ✓\n")
    else:
        print(f"\n  Test C: {len(issues)} issue(s) found")
        for iss in issues:
            print(f"    ⚠ {iss}")
        print()
    return {"issue_count": len(issues), "issues": issues}


# ── Test D ─────────────────────────────────────────────────────────────────────

_ABBREV_SET = {
    "QD", "BID", "TID", "QID", "PRN", "d/c", "f/u", "SOB",
    "HTN", "Dx", "Rx", "s/p", "w/u", "c/o", "h/o", "r/o",
}
_OCR_PATTERNS = ["rn", "0/O", "O/0", "l/1", "1/l"]


def _find_abbrevs_in_text(text: str) -> list[str]:
    """Return abbreviations from _ABBREV_SET found in the raw text."""
    found = []
    for abbrev in _ABBREV_SET:
        if abbrev in text:
            found.append(abbrev)
    return found


def run_test_d() -> dict:
    """
    Test D: False extraction-warning rate on all 10 clean original PDFs.
    Target: 0 false warnings.
    """
    print("\n" + "═" * 72)
    print("  TEST D — False Warning Rate (10 original PDFs)")
    print("═" * 72)

    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    abbrev_fires: list[str] = []
    ocr_fires: list[str] = []
    first_call = True

    _abbrev_warning_fragment = "abbreviated clinical shorthand"
    _ocr_warning_fragment = "OCR artifacts"

    print(f"\n  {'PDF':<30} {'Abbrev warning':<16} {'OCR warning':<16}")
    _hr()

    for pdf_path in clean_files:
        if not first_call:
            time.sleep(_INTER_CALL_DELAY)
        first_call = False

        pdf_text = extract_text_from_pdf(str(pdf_path))
        result, error = _run(pdf_path)

        if error or result is None:
            print(f"  {pdf_path.name:<30} ERROR")
            continue

        warnings = result.extraction_warnings
        fired_abbrev = any(_abbrev_warning_fragment in w for w in warnings)
        fired_ocr = any(_ocr_warning_fragment in w for w in warnings)

        abbrev_label = "FIRED ⚠" if fired_abbrev else "ok"
        ocr_label = "FIRED ⚠" if fired_ocr else "ok"
        print(f"  {pdf_path.name:<30} {abbrev_label:<16} {ocr_label}")

        if fired_abbrev:
            found_abbrevs = _find_abbrevs_in_text(pdf_text)[:3]
            abbrev_fires.append(
                f"{pdf_path.name}: abbrevs found in text = {found_abbrevs}"
            )

        if fired_ocr:
            ocr_fires.append(f"{pdf_path.name}: OCR warning fired on clean PDF")

    _hr()
    total_false = len(abbrev_fires) + len(ocr_fires)
    clean_count = len(list(_TEST_DATA_DIR.glob("*.pdf"))) - total_false
    print(f"\n  Abbreviation warning false fires: {len(abbrev_fires)}")
    for f in abbrev_fires:
        print(f"    ⚠ {f}")
    print(f"  OCR warning false fires: {len(ocr_fires)}")
    for f in ocr_fires:
        print(f"    ⚠ {f}")
    print(f"  Target: 0 false warnings. Result: {total_false} false fire(s).\n")

    return {
        "abbrev_fires": abbrev_fires,
        "ocr_fires": ocr_fires,
        "total_false": total_false,
        "clean_count": clean_count,
    }


# ── Test E ─────────────────────────────────────────────────────────────────────

def run_test_e() -> dict:
    """
    Test E: Procedures completeness — pdfplumber bullet count vs Agent 1 count.
    """
    print("\n" + "═" * 72)
    print("  TEST E — Procedures Completeness (10 PDFs)")
    print("═" * 72)

    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    mismatches: list[str] = []
    first_call = True

    print(f"\n  {'PDF':<30} {'Raw count':<12} {'Agent 1':<12} Match?")
    _hr()

    for pdf_path in clean_files:
        if not first_call:
            time.sleep(_INTER_CALL_DELAY)
        first_call = False

        raw_count = _count_procedure_bullets(pdf_path)
        result, error = _run(pdf_path)

        if error or result is None:
            print(f"  {pdf_path.name:<30} ERROR")
            mismatches.append(f"{pdf_path.name}: agent error")
            continue

        agent_count = len(result.procedures_performed)

        if agent_count == raw_count:
            match_label = "YES"
        elif agent_count < raw_count:
            match_label = f"PARTIAL (missed {raw_count - agent_count})"
            mismatches.append(
                f"{pdf_path.name}: raw={raw_count}, agent={agent_count} "
                f"— missed {raw_count - agent_count} procedure(s)"
            )
        else:
            match_label = f"OVER (extra {agent_count - raw_count})"
            mismatches.append(
                f"{pdf_path.name}: raw={raw_count}, agent={agent_count} "
                f"— {agent_count - raw_count} possible fabrication(s)"
            )

        print(f"  {pdf_path.name:<30} {raw_count:<12} {agent_count:<12} {match_label}")

    _hr()
    match_count = len(clean_files) - len(mismatches)
    if not mismatches:
        print(f"\n  Test E: 10/10 match ✓\n")
    else:
        print(f"\n  Test E: {match_count}/{len(clean_files)} match")
        for m in mismatches:
            print(f"    ⚠ {m}")
        print()

    return {"match_count": match_count, "total": len(clean_files), "mismatches": mismatches}


# ── Final report ───────────────────────────────────────────────────────────────

def _print_final_report(
    ta: dict, tb: dict, tc: dict, td: dict, te: dict
) -> None:
    """Print the consolidated summary table and flag anything needing a prompt fix."""

    print("\n" + "═" * 80)
    print("  FINAL REPORT — Agent 1 Prompt Verification")
    print("═" * 80)

    col = (6, 36, 20)
    print(f"  {'Test':<{col[0]}} {'What it checked':<{col[1]}} {'Result':<{col[2]}} Issues found")
    _hr(80)

    rows = [
        (
            "A",
            "4 regression PDFs",
            f"{ta['pass_count']}/{ta['total']} pass",
            "; ".join(
                f"{d['filename']}: {', '.join(d['failures'])}"
                for d in ta["details"] if d["failures"]
            ) or "None",
        ),
        (
            "B",
            "Status validity (10 PDFs)",
            f"{tb['issue_count']} issues",
            "; ".join(tb["issues"][:3]) + ("…" if len(tb["issues"]) > 3 else "") or "None",
        ),
        (
            "C",
            "Provider contamination (10 PDFs)",
            f"{tc['issue_count']} issues",
            "; ".join(tc["issues"][:2]) + ("…" if len(tc["issues"]) > 2 else "") or "None",
        ),
        (
            "D",
            "False warning rate (10 PDFs)",
            f"{td['total_false']} false fires",
            "; ".join(td["abbrev_fires"] + td["ocr_fires"])[:80] or "None",
        ),
        (
            "E",
            "Procedures completeness (10 PDFs)",
            f"{te['match_count']}/{te['total']} match",
            "; ".join(te["mismatches"][:2]) + ("…" if len(te["mismatches"]) > 2 else "") or "None",
        ),
    ]

    for test_id, what, result_str, issues in rows:
        print(f"  {test_id:<{col[0]}} {what:<{col[1]}} {result_str:<{col[2]}} {issues}")

    print()
    _print_flags(ta, tb, tc, td, te)


def _print_flags(ta, tb, tc, td, te) -> None:
    """Print only items that still need a prompt fix."""
    flags = []

    for detail in ta["details"]:
        for failure in detail["failures"]:
            flags.append(f"[Test A] {detail['filename']}: {failure}")

    for issue in tb["issues"]:
        flags.append(f"[Test B] {issue}")

    for issue in tc["issues"]:
        flags.append(f"[Test C] {issue}")

    for fire in td["abbrev_fires"]:
        flags.append(f"[Test D] False abbreviation warning — {fire}")
    for fire in td["ocr_fires"]:
        flags.append(f"[Test D] False OCR warning — {fire}")

    for mismatch in te["mismatches"]:
        flags.append(f"[Test E] {mismatch}")

    if flags:
        print("  ── Items still needing a prompt fix ────────────────────────────────")
        for flag in flags:
            print(f"  ⚠  {flag}")
    else:
        print("  ✓  All checks passed. Agent 1 prompt is production-ready.")
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    """Run all five verification tests and print the final report."""
    import os
    print("\nAgent 1 Prompt Verification Suite")
    print(f"Provider : {os.environ.get('LLM_PROVIDER', 'openrouter')}")
    print(f"Model    : {os.environ.get('LLM_MODEL', 'default for provider')}")
    print(f"Delay    : {_INTER_CALL_DELAY}s between calls")

    ta = run_test_a()
    tb = run_test_b()
    tc = run_test_c()
    td = run_test_d()
    te = run_test_e()

    _print_final_report(ta, tb, tc, td, te)


if __name__ == "__main__":
    main()
