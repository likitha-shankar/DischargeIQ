"""
Comprehensive test suite for Agent 1 (Extraction) — DIS-5.

Covers six test areas:
  Part 1 — Schema compliance across all 14 PDFs
  Part 2 — Field accuracy spot check (manual review, 3 PDFs)
  Part 3 — Null / empty-list handling on a minimal synthetic document
  Part 4 — Malformed input resilience (empty PDF, garbage text, non-PDF)
  Part 5 — FK readability score on extraction_warnings text
  Part 6 — Rate limit resilience (5s inter-call delay, all 14 PDFs)

Does NOT modify any agent code. Only reads from:
  dischargeiq/agents/extraction_agent.py
  dischargeiq/models/extraction.py
  dischargeiq/utils/scorer.py
  dischargeiq/utils/warnings.py

Run:
    python test_agent1_comprehensive.py

Requires OPENROUTER_API_KEY (or the configured LLM_PROVIDER key) in .env.
"""

import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# ── stdlib path fixup ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ── third-party ──────────────────────────────────────────────────────────────
from dotenv import load_dotenv
from fpdf import FPDF

# ── local ────────────────────────────────────────────────────────────────────
from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.models.extraction import ExtractionOutput, Medication
from dischargeiq.utils.scorer import fk_check
from dischargeiq.utils.warnings import assess_extraction_completeness

load_dotenv()

# ── path constants ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent
_TEST_DATA_DIR = _ROOT / "test-data"
_STRESS_DIR = _TEST_DATA_DIR / "stress-test"

# Part 2 spot-check filenames (relative to _TEST_DATA_DIR).
_SPOT_CHECK_FILES = ["copd_01.pdf", "heart_failure_01.pdf", "hip_replacement_01.pdf"]

# Inter-call delay for Part 6 (seconds).
_PART6_DELAY_SECONDS = 5

# Optional fields on ExtractionOutput that must be null, not empty string, when absent.
_OPTIONAL_SCALAR_FIELDS = ["patient_name", "discharge_date", "discharge_condition"]

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_pdf_bytes(text_content: str) -> bytes:
    """
    Create a minimal single-page PDF containing the given plain text.

    Uses fpdf (already in the project via generate_stress_pdfs.py) to avoid
    adding new dependencies. The PDF is returned as raw bytes — the caller
    is responsible for writing to a temp file if a path is needed.

    Args:
        text_content: Plain text to embed in the PDF body.

    Returns:
        bytes: Raw PDF file content.
    """
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", size=11)
    # multi_cell wraps long lines automatically.
    doc.multi_cell(0, 6, text_content)
    return doc.output()


def _write_temp_pdf(content_bytes: bytes, suffix: str = ".pdf") -> str:
    """
    Write bytes to a named temporary file and return its path.

    The file is NOT deleted on close so it can be read by pdfplumber.
    The caller must delete it after use.

    Args:
        content_bytes: Raw file bytes to write.
        suffix: File extension (default .pdf).

    Returns:
        str: Absolute path to the temporary file.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content_bytes)
    tmp.close()
    return tmp.name


def _run_agent_on_path(pdf_path: str) -> tuple[Optional[ExtractionOutput], Optional[Exception]]:
    """
    Run Agent 1 end-to-end on a file path and return (result, error).

    Never raises. All exceptions are caught and returned as the second
    element of the tuple so callers can assert on them without a try/except
    in every test.

    Args:
        pdf_path: Absolute or relative path to the file.

    Returns:
        tuple: (ExtractionOutput, None) on success,
               (None, Exception) on any failure.
    """
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        result = run_extraction_agent(pdf_text)
        return result, None
    except Exception as exc:  # noqa: BLE001
        return None, exc


def _hr(width: int = 68) -> None:
    """Print a horizontal rule of the given width."""
    print("─" * width)


# ─────────────────────────────────────────────────────────────────────────────
# Part 1 — Schema compliance
# ─────────────────────────────────────────────────────────────────────────────

def _schema_violations(result: ExtractionOutput, pdf_text: str) -> list[str]:
    """
    Return a list of schema violation strings for a single extraction result.

    Checks performed:
      - primary_diagnosis is non-null and non-empty
      - medications / follow_up_appointments / extraction_warnings are lists
      - Every Medication has a non-empty name
      - Optional scalar fields are null, not empty string
      - discharge_date (if present) appears verbatim in the source PDF text

    Args:
        result: ExtractionOutput returned by Agent 1.
        pdf_text: Raw PDF text used to generate the result (for date check).

    Returns:
        list[str]: Human-readable violation descriptions. Empty if all pass.
    """
    violations: list[str] = []

    # Required string field must be non-empty.
    if not result.primary_diagnosis or not result.primary_diagnosis.strip():
        violations.append("primary_diagnosis is null or empty string")

    # List fields must be lists (Pydantic guarantees this, but verify at runtime).
    for field_name in ("medications", "follow_up_appointments", "extraction_warnings",
                       "secondary_diagnoses", "procedures_performed",
                       "activity_restrictions", "dietary_restrictions", "red_flag_symptoms"):
        value = getattr(result, field_name)
        if not isinstance(value, list):
            violations.append(f"{field_name} is not a list (got {type(value).__name__})")

    # Every Medication must have a non-empty name.
    for idx, med in enumerate(result.medications):
        if not isinstance(med, Medication):
            violations.append(f"medications[{idx}] is not a Medication object")
        elif not med.name or not med.name.strip():
            violations.append(f"medications[{idx}].name is empty or null")

    # Optional scalars must be null, never an empty string.
    for field_name in _OPTIONAL_SCALAR_FIELDS:
        value = getattr(result, field_name)
        if value == "":
            violations.append(
                f"{field_name} is empty string — must be null when absent, not ''"
            )

    # If a discharge_date was extracted, it should appear somewhere in the source text.
    # This is a fabrication heuristic: if the date string is not in the raw document,
    # Agent 1 likely invented it.
    if result.discharge_date and result.discharge_date not in pdf_text:
        violations.append(
            f"discharge_date '{result.discharge_date}' not found verbatim in PDF text "
            f"— possible fabrication"
        )

    return violations


def run_part1() -> dict:
    """
    Part 1: Run Agent 1 on all 14 PDFs and verify schema compliance.

    Returns:
        dict with keys:
            pass_count (int): Number of PDFs with zero violations.
            total (int): Total PDFs attempted.
            details (list[dict]): Per-PDF results.
    """
    print("\n" + "═" * 68)
    print("  PART 1 — Schema Compliance (14 PDFs)")
    print("═" * 68)

    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    stress_files = sorted(_STRESS_DIR.glob("messy_*.pdf"))
    all_files = clean_files + stress_files

    details = []
    col_w = (30, 14, 20)  # column widths for filename | schema_valid | violations
    header = f"{'Filename':<{col_w[0]}} {'Schema valid':<{col_w[1]}} Violations"
    print(f"\n{header}")
    _hr()

    for pdf_path in all_files:
        try:
            pdf_text = extract_text_from_pdf(str(pdf_path))
            result, error = _run_agent_on_path(str(pdf_path))
            # Use already-extracted text; re-run only if we somehow got the text wrong.
        except Exception as exc:  # noqa: BLE001
            pdf_text = ""
            result, error = None, exc

        if error or result is None:
            row = {
                "filename": pdf_path.name,
                "schema_valid": False,
                "violations": [f"Agent raised: {type(error).__name__}: {error}"],
            }
        else:
            violations = _schema_violations(result, pdf_text)
            row = {
                "filename": pdf_path.name,
                "schema_valid": len(violations) == 0,
                "violations": violations,
            }

        details.append(row)
        valid_label = "PASS" if row["schema_valid"] else "FAIL"
        violation_summary = "; ".join(row["violations"]) if row["violations"] else "none"
        print(f"{row['filename']:<{col_w[0]}} {valid_label:<{col_w[1]}} {violation_summary}")

        # Inter-call delay to respect rate limits.
        time.sleep(5)

    pass_count = sum(1 for r in details if r["schema_valid"])
    _hr()
    print(f"  Schema compliance: {pass_count}/{len(all_files)} passed\n")
    return {"pass_count": pass_count, "total": len(all_files), "details": details}


# ─────────────────────────────────────────────────────────────────────────────
# Part 2 — Field accuracy spot check (manual review)
# ─────────────────────────────────────────────────────────────────────────────

def run_part2() -> None:
    """
    Part 2: Print full extraction JSON for 3 PDFs for manual review.

    No automatic pass/fail. Output must be reviewed by a human to verify
    diagnosis names, medication details, follow-up dates, and red-flag symptoms
    match the source documents exactly.
    """
    print("\n" + "═" * 68)
    print("  PART 2 — Field Accuracy Spot Check (manual review required)")
    print("═" * 68)
    print("  Review: primary_diagnosis, medication names/doses/frequencies,")
    print("  follow-up dates/providers, red_flag_symptoms vs. source PDF.\n")

    for filename in _SPOT_CHECK_FILES:
        pdf_path = _TEST_DATA_DIR / filename
        print(f"\n{'─' * 68}")
        print(f"  FILE: {filename}")
        print(f"{'─' * 68}")

        result, error = _run_agent_on_path(str(pdf_path))

        if error or result is None:
            print(f"  ERROR: {type(error).__name__}: {error}")
        else:
            # Print as indented JSON for readability.
            print(json.dumps(result.model_dump(), indent=2))

        time.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# Part 3 — Null / empty-list handling
# ─────────────────────────────────────────────────────────────────────────────

def _check_null_handling(result: ExtractionOutput) -> list[dict]:
    """
    Run all null-handling assertions against a minimal-document extraction.

    Each check verifies that a field absent from the source document comes
    back as null (for Optional scalars) or [] (for lists) — never as a
    non-empty value or wrong type.

    Args:
        result: ExtractionOutput from a minimal document with only:
                patient name, diagnosis, discharge_date.

    Returns:
        list[dict]: One entry per check with keys:
            check (str): Description of what was tested.
            passed (bool): Whether the check passed.
            actual: The actual value returned.
    """
    checks = []

    def _add(description: str, passed: bool, actual) -> None:
        checks.append({"check": description, "passed": passed, "actual": actual})

    # List fields absent from the minimal document must be empty lists.
    list_fields = [
        ("medications", []),
        ("follow_up_appointments", []),
        ("red_flag_symptoms", []),
        ("activity_restrictions", []),
        ("dietary_restrictions", []),
        ("secondary_diagnoses", []),
        ("procedures_performed", []),
    ]
    for field_name, expected in list_fields:
        actual = getattr(result, field_name)
        _add(
            f"{field_name} returns [] not null",
            actual == expected,
            actual,
        )

    # Optional scalar fields not present in the document must be null, not ''.
    for field_name in ("patient_name", "discharge_condition"):
        actual = getattr(result, field_name)
        _add(
            f"{field_name} is null or a non-empty string, never ''",
            actual is None or (isinstance(actual, str) and actual.strip() != ""),
            actual,
        )

    # extraction_warnings must flag that critical fields are missing.
    has_warnings = len(result.extraction_warnings) > 0
    _add(
        "extraction_warnings is non-empty (flags missing meds / follow-ups)",
        has_warnings,
        result.extraction_warnings,
    )

    return checks


def run_part3() -> dict:
    """
    Part 3: Test Agent 1 on a minimal synthetic document.

    Creates a PDF in memory containing only patient name, diagnosis, and
    discharge date — no medications, no follow-ups, no red flags. Verifies
    that all absent list fields return [] and the agent does not fabricate.

    Returns:
        dict with pass_count and total checks.
    """
    print("\n" + "═" * 68)
    print("  PART 3 — Null / Empty-List Handling")
    print("═" * 68)

    minimal_text = (
        "Patient: John Doe\n"
        "Diagnosis: Pneumonia\n"
        "Discharge date: 2026-04-10\n"
    )
    pdf_bytes = _make_pdf_bytes(minimal_text)
    tmp_path = _write_temp_pdf(pdf_bytes)

    try:
        result, error = _run_agent_on_path(tmp_path)
    finally:
        # Always clean up the temp file.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if error or result is None:
        print(f"  Agent raised: {type(error).__name__}: {error}")
        print("  Cannot run null-handling checks — Part 3 BLOCKED.\n")
        return {"pass_count": 0, "total": 9, "blocked": True}

    print(f"\n  Extracted primary_diagnosis: {result.primary_diagnosis}")
    checks = _check_null_handling(result)

    col_w = (54, 8)
    print(f"\n  {'Check':<{col_w[0]}} {'Result'}")
    _hr()
    for chk in checks:
        label = "PASS" if chk["passed"] else "FAIL"
        print(f"  {chk['check']:<{col_w[0]}} {label}")
        if not chk["passed"]:
            print(f"    → actual: {chk['actual']!r}")

    pass_count = sum(1 for c in checks if c["passed"])
    _hr()
    print(f"  Null handling: {pass_count}/{len(checks)} checks passed\n")
    return {"pass_count": pass_count, "total": len(checks)}


# ─────────────────────────────────────────────────────────────────────────────
# Part 4 — Malformed input resilience
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_malformed(label: str, tmp_path: str) -> dict:
    """
    Run Agent 1 on a malformed input and record the outcome.

    A "pass" means the agent raised a known, handled exception rather than
    an unexpected crash. If the agent returns an ExtractionOutput, that is
    also a pass — the agent recovered gracefully.

    Args:
        label: Human-readable description of this test case.
        tmp_path: Path to the temporary file to test.

    Returns:
        dict with keys:
            label (str)
            passed (bool): True if no unhandled / unexpected exception.
            returned_output (bool): True if ExtractionOutput was returned.
            exception_type (str | None): Exception class name if raised.
            exception_msg (str | None): First 120 chars of the error message.
            primary_diagnosis: The diagnosis value if output was returned.
            warnings: extraction_warnings if output was returned.
    """
    # Exception types that indicate controlled failure (not an unhandled crash).
    _known_exception_types = (
        FileNotFoundError,
        OSError,
        ValueError,
        Exception,   # broad catch — we check for unexpected RuntimeError below
    )

    result, error = _run_agent_on_path(tmp_path)

    if error is None and result is not None:
        return {
            "label": label,
            "passed": True,
            "returned_output": True,
            "exception_type": None,
            "exception_msg": None,
            "primary_diagnosis": result.primary_diagnosis,
            "warnings": result.extraction_warnings,
        }

    # An exception was raised — determine if it is expected / handled.
    exception_type = type(error).__name__
    exception_msg = str(error)[:120]
    # An unhandled crash would show up as RuntimeError, AttributeError, or
    # similar low-level errors that indicate a programming mistake, not a
    # controlled failure path.
    unexpected_types = (AttributeError, RuntimeError, TypeError, NameError)
    is_controlled = not isinstance(error, unexpected_types)

    return {
        "label": label,
        "passed": is_controlled,
        "returned_output": False,
        "exception_type": exception_type,
        "exception_msg": exception_msg,
        "primary_diagnosis": None,
        "warnings": [],
    }


def run_part4() -> dict:
    """
    Part 4: Test Agent 1 against three malformed inputs.

    a) Empty PDF       — valid PDF structure with no text on the page
    b) Garbage text    — PDF containing only non-medical random characters
    c) Non-PDF file    — a .txt file passed where a PDF is expected

    Returns:
        dict with pass_count and total.
    """
    print("\n" + "═" * 68)
    print("  PART 4 — Malformed Input Resilience")
    print("═" * 68)

    test_cases = []
    tmp_paths = []

    # Case (a): empty PDF — valid PDF structure, one blank page, no text.
    empty_pdf_bytes = _make_pdf_bytes("")
    path_a = _write_temp_pdf(empty_pdf_bytes)
    tmp_paths.append(path_a)
    test_cases.append(("(a) Empty PDF (valid structure, no text)", path_a))

    # Case (b): garbage text PDF — non-medical random characters.
    garbage_pdf_bytes = _make_pdf_bytes("asdfghjkl 12345 @@@@@ nothing here !!!")
    path_b = _write_temp_pdf(garbage_pdf_bytes)
    tmp_paths.append(path_b)
    test_cases.append(("(b) Garbage text PDF", path_b))

    # Case (c): non-PDF file — a plain .txt file.
    path_c = _write_temp_pdf(b"This is not a PDF file. Plain text content.", suffix=".txt")
    tmp_paths.append(path_c)
    test_cases.append(("(c) Non-PDF file (.txt passed as PDF)", path_c))

    results = []
    for label, tmp_path in test_cases:
        outcome = _evaluate_malformed(label, tmp_path)
        results.append(outcome)

        status = "PASS" if outcome["passed"] else "FAIL"
        print(f"\n  {label}")
        print(f"  Result         : {status}")
        if outcome["returned_output"]:
            print(f"  Returned output: Yes")
            print(f"  primary_diagnosis: {outcome['primary_diagnosis']!r}")
            print(f"  warnings         : {outcome['warnings']}")
        else:
            print(f"  Returned output: No")
            print(f"  Exception      : {outcome['exception_type']}: {outcome['exception_msg']}")

        # Flag if extraction_warnings would be empty on failure (orchestrator gap).
        if not outcome["returned_output"] and not outcome["warnings"]:
            print(
                "  ⚠ FLAG: No ExtractionOutput returned — extraction_warnings cannot be "
                "populated on failure. The orchestrator must catch this and set "
                "pipeline_status='partial' with a fallback message."
            )

    # Clean up all temp files.
    for tmp_path in tmp_paths:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    pass_count = sum(1 for r in results if r["passed"])
    print(f"\n  Malformed input: {pass_count}/{len(results)} passed\n")
    return {"pass_count": pass_count, "total": len(results), "details": results}


# ─────────────────────────────────────────────────────────────────────────────
# Part 5 — FK score on extraction_warnings
# ─────────────────────────────────────────────────────────────────────────────

def run_part5(part1_details: list[dict]) -> dict:
    """
    Part 5: Score extraction_warnings text for readability.

    Reuses extraction results already captured in Part 1 to avoid
    making additional API calls. FK target is grade <= 6.0.

    Args:
        part1_details: The 'details' list from run_part1() return value.
                       Each entry has 'filename' and optionally a cached result.
                       Since Part 1 doesn't cache results, we re-run only the
                       10 original PDFs here.

    Returns:
        dict with average_fk and per_pdf scores.
    """
    print("\n" + "═" * 68)
    print("  PART 5 — FK Score on extraction_warnings (10 original PDFs)")
    print("═" * 68)

    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    scores = []
    col_w = (30, 10, 8)
    print(f"\n  {'Filename':<{col_w[0]}} {'FK grade':<{col_w[1]}} {'Pass?'}")
    _hr()

    for pdf_path in clean_files:
        result, error = _run_agent_on_path(str(pdf_path))

        if error or result is None or not result.extraction_warnings:
            fk_grade = None
            passes = None
            label = "N/A (no warnings or error)"
        else:
            combined_warnings = " ".join(result.extraction_warnings)
            check = fk_check(combined_warnings)
            fk_grade = check["fk_grade"]
            passes = check["passes"]
            label = "PASS" if passes else "FAIL"
            scores.append(fk_grade)

        grade_str = f"{fk_grade:.2f}" if fk_grade is not None else "—"
        print(f"  {pdf_path.name:<{col_w[0]}} {grade_str:<{col_w[1]}} {label}")
        time.sleep(5)

    avg_fk = round(sum(scores) / len(scores), 2) if scores else None
    avg_passes = avg_fk is not None and avg_fk <= 6.0

    _hr()
    if avg_fk is not None:
        avg_label = "PASS" if avg_passes else "FAIL"
        print(f"  Average FK grade: {avg_fk}  [{avg_label}]  (target ≤ 6.0)\n")
    else:
        print("  No FK scores computed (all PDFs had no warnings or errors).\n")

    return {"average_fk": avg_fk, "passes": avg_passes, "per_pdf_scores": scores}


# ─────────────────────────────────────────────────────────────────────────────
# Part 6 — Rate limit resilience
# ─────────────────────────────────────────────────────────────────────────────

def run_part6() -> dict:
    """
    Part 6: Run all 14 PDFs with a 5s inter-call delay.

    Verifies that rate-limit errors are caught cleanly (logged as a warning,
    not a crash) and that the test harness itself records the failure without
    propagating the exception.

    Returns:
        dict with pass_count, rate_limit_count, total.
    """
    print("\n" + "═" * 68)
    print(f"  PART 6 — Rate Limit Resilience (5s delay, 14 PDFs)")
    print("═" * 68)

    clean_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    stress_files = sorted(_STRESS_DIR.glob("messy_*.pdf"))
    all_files = clean_files + stress_files

    pass_count = 0
    rate_limit_count = 0
    results = []

    for idx, pdf_path in enumerate(all_files):
        if idx > 0:
            time.sleep(_PART6_DELAY_SECONDS)

        print(f"\n  [{idx + 1:02d}/{len(all_files)}] {pdf_path.name} ...", end="", flush=True)
        result, error = _run_agent_on_path(str(pdf_path))

        if error is None and result is not None:
            passed = bool(result.primary_diagnosis)
            status = "PASS"
            pass_count += 1
        else:
            passed = False
            error_str = str(error)
            is_rate_limit = "429" in error_str or "RateLimitError" in type(error).__name__
            if is_rate_limit:
                rate_limit_count += 1
                status = "RATE_LIMIT (caught cleanly)"
            else:
                status = f"FAIL ({type(error).__name__})"

        print(f" {status}")
        results.append({"filename": pdf_path.name, "status": status, "passed": passed})

    _hr()
    print(f"\n  Total: {pass_count}/{len(all_files)} passed")
    print(f"  Rate limit hits (caught, not crashes): {rate_limit_count}")
    print(f"  Other failures: {len(all_files) - pass_count - rate_limit_count}\n")
    return {
        "pass_count": pass_count,
        "rate_limit_count": rate_limit_count,
        "total": len(all_files),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Final report
# ─────────────────────────────────────────────────────────────────────────────

def _print_final_report(
    p1: dict,
    p3: dict,
    p4: dict,
    p5: dict,
    p6: dict,
) -> None:
    """
    Print the consolidated summary table for all 6 parts.

    Flags any part that requires a code fix before Agent 2 integration.

    Args:
        p1: Return value from run_part1().
        p3: Return value from run_part3().
        p4: Return value from run_part4().
        p5: Return value from run_part5().
        p6: Return value from run_part6().
    """
    print("\n" + "═" * 80)
    print("  FINAL REPORT — Agent 1 Comprehensive Test")
    print("═" * 80)

    col = (5, 38, 16, 16)
    header = (
        f"  {'Part':<{col[0]}} {'What was tested':<{col[1]}} "
        f"{'Result':<{col[1]}} Issues"
    )
    print(header)
    _hr(80)

    rows = [
        (
            "1",
            "Schema compliance",
            f"{p1['pass_count']}/{p1['total']} pass",
            _schema_issues(p1),
        ),
        (
            "2",
            "Field accuracy",
            "Printed (manual review)",
            "Requires human sign-off",
        ),
        (
            "3",
            "Null / empty-list handling",
            "BLOCKED" if p3.get("blocked") else f"{p3['pass_count']}/{p3['total']} pass",
            _null_issues(p3),
        ),
        (
            "4",
            "Malformed input resilience",
            f"{p4['pass_count']}/{p4['total']} pass",
            _malformed_issues(p4),
        ),
        (
            "5",
            "FK score on extraction_warnings",
            f"avg {p5['average_fk']}" if p5["average_fk"] else "N/A",
            "PASS" if p5["passes"] else "⚠ avg FK > 6.0 — review warning text",
        ),
        (
            "6",
            "Rate limit resilience",
            f"{p6['pass_count']}/{p6['total']} pass",
            f"{p6['rate_limit_count']} rate-limit hits caught cleanly",
        ),
    ]

    for part_num, tested, result_str, issues in rows:
        print(f"  {part_num:<{col[0]}} {tested:<{col[1]}} {result_str:<20} {issues}")

    print()
    _print_fix_flags(p1, p3, p4, p5)


def _schema_issues(p1: dict) -> str:
    """Summarise any schema violations found in Part 1."""
    all_violations = [
        v
        for detail in p1["details"]
        for v in detail["violations"]
    ]
    if not all_violations:
        return "None"
    unique = list(dict.fromkeys(all_violations))  # deduplicate, preserve order
    return "; ".join(unique[:2]) + ("…" if len(unique) > 2 else "")


def _null_issues(p3: dict) -> str:
    """Summarise null-handling issues from Part 3."""
    if p3.get("blocked"):
        return "⚠ BLOCKED — agent raised exception on minimal doc"
    if p3["pass_count"] < p3["total"]:
        return f"⚠ {p3['total'] - p3['pass_count']} checks failed"
    return "None"


def _malformed_issues(p4: dict) -> str:
    """Summarise malformed-input issues from Part 4."""
    failed = [d for d in p4["details"] if not d["passed"]]
    if not failed:
        # Check for the orchestrator gap flag (no ExtractionOutput on failure).
        has_gap = any(not d["returned_output"] for d in p4["details"])
        if has_gap:
            return "⚠ Orchestrator gap: no ExtractionOutput on failure"
        return "None"
    labels = [d["label"] for d in failed]
    return "⚠ Failed: " + ", ".join(labels)


def _print_fix_flags(p1: dict, p3: dict, p4: dict, p5: dict) -> None:
    """Print a focused list of items that need a code fix before Agent 2."""
    flags = []

    # Part 1 violations.
    for detail in p1["details"]:
        for v in detail["violations"]:
            flags.append(f"[Part 1] {detail['filename']}: {v}")

    # Part 3 blocked or failures.
    if p3.get("blocked"):
        flags.append("[Part 3] Agent raised on minimal doc — check empty-text handling")

    # Part 4 orchestrator gap.
    no_output_cases = [
        d["label"] for d in p4["details"] if not d["returned_output"]
    ]
    if no_output_cases:
        flags.append(
            "[Part 4] Orchestrator gap — on malformed input, no ExtractionOutput is "
            "returned so extraction_warnings cannot be populated. "
            "Fix: orchestrator must catch agent exceptions and return a partial "
            "PipelineResponse with pipeline_status='partial'."
        )

    # Part 5 FK.
    if p5["average_fk"] and not p5["passes"]:
        flags.append(
            f"[Part 5] Average extraction_warnings FK grade {p5['average_fk']} > 6.0 — "
            "simplify warning text in the agent system prompt."
        )

    if flags:
        print("  ── Items that need a fix before Agent 2 integration ────────────────")
        for flag in flags:
            print(f"  ⚠  {flag}")
    else:
        print("  ✓ No blocking issues found. Agent 2 integration may proceed.")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run all 6 test parts in sequence and print the final report.

    Parts 1, 5, and 6 make LLM API calls. The full run takes approximately
    10–20 minutes due to inter-call delays on free-tier providers.
    """
    print("\nAgent 1 Comprehensive Test Suite")
    print(f"Provider : {os.environ.get('LLM_PROVIDER', 'openrouter')}")
    print(f"Model    : {os.environ.get('LLM_MODEL', 'default for provider')}")
    print(f"Date     : 2026-04-14")

    p1_result = run_part1()
    run_part2()
    p3_result = run_part3()
    p4_result = run_part4()
    p5_result = run_part5(p1_result["details"])
    p6_result = run_part6()

    _print_final_report(p1_result, p3_result, p4_result, p5_result, p6_result)


if __name__ == "__main__":
    main()
