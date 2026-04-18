"""
test_agents_1_2.py — End-to-end test suite for Agents 1 and 2 together.

Five sections:

  S1 — Full pipeline on all 10 synthetic PDFs. Detailed per-PDF output block
       with Agent 1 extraction fields and Agent 2 explanation text + FK grade.

  S2 — Content quality checks on the same 10 PDFs (no new LLM calls):
       word length, unexplained jargon, medication-change language, sentence
       completeness, and fabricated clinical statistics.

  S3 — Pipeline resilience: 4 edge-case PDFs built in memory with fpdf2.
       Tests very short diagnosis, complex multi-word diagnosis, Agent 1 partial
       failure guard, and multiple secondary diagnoses.

  S4 — FK score analysis across all 10 PDFs from S1. Prints distribution,
       best/worst documents, and the full text of the highest-scoring explanation
       for manual review.

  S5 — Schema contract verification across all PipelineResponse objects
       produced in S1 and S3.

A 12-second delay is enforced between every run_pipeline() call.

Run:
    python test_agents_1_2.py

Requires OPENROUTER_API_KEY (or the configured LLM_PROVIDER key) in .env.
"""

import os
import re
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
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.pipeline.orchestrator import run_pipeline

load_dotenv(dotenv_path=".env")

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_TEST_DATA_DIR = Path(__file__).parent / "test-data"
_INTER_CALL_DELAY_SECONDS = 12

# Valid pipeline status values per the PipelineResponse contract.
_VALID_STATUSES = {"complete", "partial"}

# Jargon terms to check for unexplained use in Agent 2 output.
_JARGON_TERMS = [
    "ejection fraction", "systolic", "diastolic", "exacerbation",
    "myocardial", "infarction", "arthroplasty", "avascular necrosis",
    "laparoscopic", "anastomosis",
]

# Phrases that would instruct the patient to change a medication — prohibited
# in any agent output per CLAUDE.md hard rules.
_MED_CHANGE_PHRASES = [
    "stop taking", "do not take", "discontinue",
    "increase your dose", "decrease your dose", "change your medication",
]

# Tokens that indicate an explanation follows the jargon term.
_EXPLANATION_INDICATORS = [
    "(", ", which", ", meaning", " means ", " is when", ", or",
    " — ", " - ", "in other words", "that is",
]

# Module-level timestamp for inter-call delay enforcement.
_last_call_time: float = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Core pipeline helper — never raises
# ──────────────────────────────────────────────────────────────────────────────

def _run(pdf_path: str, label: str) -> tuple[Optional[PipelineResponse], Optional[str]]:
    """
    Run the full pipeline on a PDF, enforcing a 12-second inter-call delay.
    Never raises — returns (response, None) on success or (None, error) on failure.

    Args:
        pdf_path: Path to the PDF file.
        label:    Human-readable name printed to stdout.

    Returns:
        (PipelineResponse, None) on success.
        (None, error_string) on failure.
    """
    global _last_call_time

    elapsed = time.time() - _last_call_time
    if _last_call_time > 0 and elapsed < _INTER_CALL_DELAY_SECONDS:
        wait = _INTER_CALL_DELAY_SECONDS - elapsed
        print(f"  [rate limit] sleeping {wait:.1f}s ...", flush=True)
        time.sleep(wait)

    print(f"  Running pipeline: {label} ...", end="", flush=True)
    try:
        response = run_pipeline(pdf_path)
        _last_call_time = time.time()
        print(" done")
        return response, None
    except Exception as exc:  # noqa: BLE001
        _last_call_time = time.time()
        print(" ERROR")
        return None, f"{type(exc).__name__}: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# PDF builder for Section 3 edge cases
# ──────────────────────────────────────────────────────────────────────────────

def _build_pdf(text: str) -> str:
    """
    Write plain ASCII text to a single-page PDF with fpdf2.
    Returns the path to a temporary file. Caller must delete it.

    Args:
        text: Plain ASCII text to embed. May be empty (for adversarial tests).

    Returns:
        Absolute path to the temporary .pdf file.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    if text.strip():
        pdf.multi_cell(0, 6, text)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    pdf.output(tmp.name)
    return tmp.name


# ──────────────────────────────────────────────────────────────────────────────
# Schema and content checkers
# ──────────────────────────────────────────────────────────────────────────────

def _check_a1_schema(extraction: ExtractionOutput) -> list[str]:
    """
    Verify the ExtractionOutput matches the locked Agent 1 schema contract.

    Checks:
    - primary_diagnosis is a non-empty string
    - All list fields are actually lists
    - All medication names are non-empty
    - All medication statuses are from the valid set

    Args:
        extraction: ExtractionOutput from Agent 1.

    Returns:
        List of violation strings. Empty means schema-compliant.
    """
    violations = []
    valid_statuses = {"new", "changed", "continued", "discontinued", None}

    if not isinstance(extraction.primary_diagnosis, str) or not extraction.primary_diagnosis.strip():
        violations.append("primary_diagnosis missing or empty")

    for field in ("secondary_diagnoses", "procedures_performed", "medications",
                  "follow_up_appointments", "activity_restrictions",
                  "dietary_restrictions", "red_flag_symptoms", "extraction_warnings"):
        val = getattr(extraction, field)
        if not isinstance(val, list):
            violations.append(f"{field}: expected list, got {type(val).__name__}")

    for i, med in enumerate(extraction.medications):
        if not med.name or not med.name.strip():
            violations.append(f"medications[{i}].name is empty")
        if med.status not in valid_statuses:
            violations.append(f"medications[{i}] {med.name!r}: invalid status {med.status!r}")

    return violations


def _word_count(text: str) -> int:
    """Return the number of whitespace-delimited words in text."""
    return len(text.split())


def _sentence_count(text: str) -> int:
    """
    Estimate sentence count by counting sentence-ending punctuation tokens.
    Handles abbreviations imperfectly but is sufficient for FK-level analysis.
    """
    return len(re.findall(r'[.!?]+(?:\s|$)', text))


def _check_jargon(text: str) -> list[str]:
    """
    Return a list of jargon terms that appear in text without an adjacent
    explanation clause (parenthetical, comma clause, or definition phrase).

    A term is considered explained if any _EXPLANATION_INDICATORS token appears
    within 100 characters after the term.

    Args:
        text: Agent 2 diagnosis explanation.

    Returns:
        List of unexplained jargon terms.
    """
    text_lower = text.lower()
    flagged = []
    for term in _JARGON_TERMS:
        if term not in text_lower:
            continue
        idx = text_lower.find(term)
        context = text_lower[idx + len(term): idx + len(term) + 100]
        explained = any(ind in context for ind in _EXPLANATION_INDICATORS)
        if not explained:
            flagged.append(term)
    return flagged


def _check_med_change_language(text: str) -> list[str]:
    """
    Return any prohibited medication-change phrases found in the explanation.

    Per CLAUDE.md hard rules, agents must never instruct patients to stop
    or change a medication.

    Args:
        text: Agent 2 diagnosis explanation.

    Returns:
        List of matched prohibited phrases.
    """
    text_lower = text.lower()
    return [phrase for phrase in _MED_CHANGE_PHRASES if phrase in text_lower]


def _check_fabricated_stats(text: str, extraction: ExtractionOutput) -> list[str]:
    """
    Flag percentages and clinical measurement values in the explanation that
    do not appear in any ExtractionOutput field.

    Only checks percentages (e.g. "45%") and explicit clinical units
    (mg/dL, mmHg, bpm, g/dL, mEq/L) — not general numbers like "2 weeks"
    which represent medical knowledge rather than patient-specific statistics.

    Args:
        text:       Agent 2 diagnosis explanation.
        extraction: ExtractionOutput from Agent 1 for the same document.

    Returns:
        List of flagged values with context.
    """
    # Build a searchable string from all extraction field values.
    extraction_text = " ".join(filter(None, [
        extraction.primary_diagnosis,
        " ".join(extraction.secondary_diagnoses),
        " ".join(extraction.procedures_performed),
        " ".join(m.name or "" for m in extraction.medications),
        " ".join(m.dose or "" for m in extraction.medications),
    ])).lower()

    # Match percentages and clinical measurements in the explanation.
    clinical_pattern = re.compile(
        r'(\d+\.?\d*)\s*%'
        r'|(\d+\.?\d*)\s*(?:mg/dL|mmHg|bpm|g/dL|mEq/L)',
        re.IGNORECASE,
    )

    flagged = []
    for match in clinical_pattern.finditer(text):
        num = match.group(1) or match.group(2)
        full_match = match.group(0)
        if num not in extraction_text:
            flagged.append(f'"{full_match}" not found in extraction fields')
    return flagged


def _check_pipeline_contract(label: str, response: PipelineResponse) -> list[str]:
    """
    Verify the contract between Agent 1, Agent 2, and PipelineResponse.

    Checks:
    a) extraction.primary_diagnosis is non-empty (was Agent 2's input)
    b) diagnosis_explanation is a string (never None)
    c) fk_scores is a dict; if pipeline is complete, must contain "agent2"
    d) pipeline_status is "complete" or "partial"
    e) No PipelineResponse string field is None

    Args:
        label:    Document label for error prefixing.
        response: PipelineResponse from run_pipeline().

    Returns:
        List of contract violation strings. Empty means fully compliant.
    """
    violations = []

    # (a) primary_diagnosis must always be non-empty
    if not response.extraction.primary_diagnosis:
        violations.append(f"{label}: extraction.primary_diagnosis is empty")

    # (b) diagnosis_explanation must be a string
    if not isinstance(response.diagnosis_explanation, str):
        violations.append(
            f"{label}: diagnosis_explanation is {type(response.diagnosis_explanation).__name__}, expected str"
        )

    # (c) fk_scores must be a dict; "agent2" key required on complete pipelines
    if not isinstance(response.fk_scores, dict):
        violations.append(f"{label}: fk_scores is not a dict")
    elif response.pipeline_status == "complete" and "agent2" not in response.fk_scores:
        violations.append(f"{label}: fk_scores missing 'agent2' key on complete pipeline")

    # (d) pipeline_status must be one of the two valid values
    if response.pipeline_status not in _VALID_STATUSES:
        violations.append(
            f"{label}: pipeline_status={response.pipeline_status!r}, expected 'complete' or 'partial'"
        )

    # (e) string fields must not be None
    for field in ("diagnosis_explanation", "medication_rationale",
                  "recovery_trajectory", "escalation_guide"):
        val = getattr(response, field)
        if val is None:
            violations.append(f"{label}: {field} is None, expected str")

    return violations


# ──────────────────────────────────────────────────────────────────────────────
# Section 1 — Full pipeline on 10 synthetic PDFs
# ──────────────────────────────────────────────────────────────────────────────

def run_section_1() -> dict:
    """
    Run the full pipeline on every PDF in test-data/ and print a detailed block
    per document. Returns results for reuse in Sections 2, 4, and 5.

    Pass criteria per document (all must hold):
      - Agent 1 schema valid (no violations)
      - Agent 2 FK grade <= 6.0
      - pipeline_status == "complete"
      - No extraction_warnings from completeness check

    Returns:
        dict with keys:
          results  (list[dict]) — one dict per PDF with all fields
          passed   (int)
          total    (int)
          issues   (list[str])
    """
    print("\n" + "=" * 70)
    print("SECTION 1 — Full pipeline on 10 synthetic PDFs")
    print("=" * 70)

    pdf_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    results = []
    passed = 0
    issues = []

    for pdf_path in pdf_files:
        response, error = _run(str(pdf_path), pdf_path.name)

        rec = {
            "filename": pdf_path.name,
            "response": response,
            "error": error,
            "schema_violations": [],
            "fk_grade": None,
            "fk_passes": False,
            "word_count": 0,
            "sentence_count": 0,
            "verdict": "FAIL",
            "fail_reasons": [],
        }

        print(f"\n{'=' * 10} {pdf_path.name} {'=' * 10}")

        if error:
            print(f"  ERROR: {error}")
            issues.append(f"{pdf_path.name}: pipeline error — {error}")
            results.append(rec)
            continue

        ext = response.extraction
        expl = response.diagnosis_explanation

        # ── Agent 1 output block ──────────────────────────────────────────────
        print("\n  AGENT 1 OUTPUT:")
        print(f"    patient_name       : {ext.patient_name or '(none)'}")
        print(f"    primary_diagnosis  : {ext.primary_diagnosis}")
        sec = ext.secondary_diagnoses
        print(f"    secondary_diagnoses: ({len(sec)}) {sec if sec else '[]'}")
        print(f"    medications        : ({len(ext.medications)})")
        for med in ext.medications:
            print(
                f"      - {med.name} | {med.dose or '-'} | "
                f"{med.frequency or '-'} | {med.status or '-'}"
            )
        print(f"    follow_up_appts    : ({len(ext.follow_up_appointments)})")
        for appt in ext.follow_up_appointments:
            print(
                f"      - {appt.provider or '(no provider)'} | "
                f"{appt.specialty or '-'} | {appt.date or '-'}"
            )
        print(f"    procedures         : ({len(ext.procedures_performed)})")
        print(f"    red_flag_symptoms  : ({len(ext.red_flag_symptoms)})")
        if ext.extraction_warnings:
            print(f"    extraction_warnings: {ext.extraction_warnings}")
        else:
            print(f"    extraction_warnings: none")
        print(f"    pipeline_status    : {response.pipeline_status}")

        # ── Agent 2 output block ──────────────────────────────────────────────
        wc = _word_count(expl)
        sc = _sentence_count(expl)
        fk = response.fk_scores.get("agent2", {})
        fk_grade = fk.get("fk_grade")
        fk_passes = fk.get("passes", False)

        rec["fk_grade"] = fk_grade
        rec["fk_passes"] = fk_passes
        rec["word_count"] = wc
        rec["sentence_count"] = sc

        print("\n  AGENT 2 OUTPUT:")
        print("    --- Diagnosis Explanation ---")
        # Print explanation indented, wrapped at ~70 chars per visual line
        for chunk in [expl[i:i+70] for i in range(0, len(expl), 70)]:
            print(f"    {chunk}")
        print("    ---")
        print(f"    fk_grade           : {fk_grade}")
        print(f"    passes FK (<= 6.0) : {'yes' if fk_passes else 'no'}")
        print(f"    word count         : {wc}")
        print(f"    sentence count     : {sc}")

        # ── Combined checks ───────────────────────────────────────────────────
        schema_violations = _check_a1_schema(ext)
        rec["schema_violations"] = schema_violations

        schema_ok     = len(schema_violations) == 0
        a2_not_empty  = bool(expl.strip())
        status_ok     = response.pipeline_status == "complete"
        no_warnings   = len(response.extraction_warnings) == 0

        fail_reasons = []
        if not schema_ok:
            fail_reasons.append(f"A1 schema violations: {schema_violations}")
        if not a2_not_empty:
            fail_reasons.append("A2 explanation is empty")
        if not fk_passes:
            fail_reasons.append(f"A2 FK fail: {fk_grade}")
        if not status_ok:
            fail_reasons.append(f"pipeline_status={response.pipeline_status!r}")
        if not no_warnings:
            fail_reasons.append(f"extraction_warnings: {response.extraction_warnings}")

        verdict = "PASS" if not fail_reasons else "FAIL"
        rec["verdict"] = verdict
        rec["fail_reasons"] = fail_reasons
        if verdict == "PASS":
            passed += 1
        else:
            issues.extend(f"{pdf_path.name}: {r}" for r in fail_reasons)

        print("\n  COMBINED CHECKS:")
        print(f"    A1 schema valid         : {'yes' if schema_ok else 'no'}")
        print(f"    A2 text not empty       : {'yes' if a2_not_empty else 'no'}")
        print(f"    A2 FK passes            : {'yes' if fk_passes else 'no'}")
        print(f"    pipeline_status complete: {'yes' if status_ok else 'no'}")
        print(f"    No extraction_warnings  : {'yes' if no_warnings else 'no'}")
        print(f"\n  VERDICT: {verdict}" + (f" — {'; '.join(fail_reasons)}" if fail_reasons else ""))

        results.append(rec)

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("SECTION 1 SUMMARY TABLE")
    print(f"{'=' * 70}")
    col = [24, 10, 7, 9, 10, 8]
    hdr = (
        f"  {'PDF':<{col[0]}} {'A1 schema':<{col[1]}} {'A2 FK':<{col[2]}} "
        f"{'A2 words':<{col[3]}} {'pipeline':<{col[4]}} {'verdict':<{col[5]}}"
    )
    print(hdr)
    print("  " + "-" * (sum(col) + 5 * 1))
    for rec in results:
        if rec["error"]:
            row_fk = "err"
            row_schema = "err"
            row_words = "err"
            row_pipeline = "err"
        else:
            row_schema = "yes" if not rec["schema_violations"] else "NO"
            row_fk = f"{rec['fk_grade']:.1f}" if rec["fk_grade"] is not None else "n/a"
            row_words = str(rec["word_count"])
            row_pipeline = rec["response"].pipeline_status if rec["response"] else "err"
        print(
            f"  {rec['filename']:<{col[0]}} {row_schema:<{col[1]}} {row_fk:<{col[2]}} "
            f"{row_words:<{col[3]}} {row_pipeline:<{col[4]}} {rec['verdict']:<{col[5]}}"
        )

    schema_valid_count = sum(1 for r in results if not r["schema_violations"] and not r["error"])
    fk_pass_count      = sum(1 for r in results if r["fk_passes"])
    complete_count     = sum(1 for r in results if r["response"] and r["response"].pipeline_status == "complete")

    print(f"\n  Total PDFs          : {len(results)}")
    print(f"  A1 schema valid     : {schema_valid_count}/{len(results)}")
    print(f"  A2 FK passes        : {fk_pass_count}/{len(results)}")
    print(f"  Pipeline complete   : {complete_count}/{len(results)}")
    print(f"  Overall pass        : {passed}/{len(results)}")

    return {
        "results": results,
        "passed": passed,
        "total": len(results),
        "issues": issues,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Section 2 — Content quality checks (no new LLM calls)
# ──────────────────────────────────────────────────────────────────────────────

def run_section_2(s1_results: list[dict]) -> dict:
    """
    Run content quality checks on the Agent 2 explanations from Section 1.
    No new LLM calls are made — all analysis is pure Python string operations.

    Checks per explanation:
      a) Length 50-300 words
      b) No unexplained jargon terms
      c) No medication-change language
      d) Ends with a complete sentence (., !, or ?)
      e) No fabricated clinical statistics

    Args:
        s1_results: The results list from run_section_1().

    Returns:
        dict with keys: passed (int), total (int), issues (list[str]),
        per_check counts for the final report.
    """
    print(f"\n{'=' * 70}")
    print("SECTION 2 — Agent 2 content quality checks")
    print(f"{'=' * 70}")

    passed = 0
    issues = []
    counts = {"length": 0, "jargon": 0, "med_change": 0, "sentence": 0}

    col = [24, 10, 14, 16, 19, 8]
    hdr = (
        f"  {'PDF':<{col[0]}} {'length OK':<{col[1]}} {'jargon clean':<{col[2]}} "
        f"{'no med changes':<{col[3]}} {'complete sentence':<{col[4]}} {'verdict':<{col[5]}}"
    )
    print(hdr)
    print("  " + "-" * (sum(col) + 5))

    for rec in s1_results:
        fname = rec["filename"]
        if rec["error"] or rec["response"] is None:
            print(
                f"  {fname:<{col[0]}} {'skip':<{col[1]}} {'skip':<{col[2]}} "
                f"{'skip':<{col[3]}} {'skip':<{col[4]}} {'skip':<{col[5]}}"
            )
            continue

        expl = rec["response"].diagnosis_explanation
        ext  = rec["response"].extraction

        if not expl.strip():
            print(
                f"  {fname:<{col[0]}} {'n/a':<{col[1]}} {'n/a':<{col[2]}} "
                f"{'n/a':<{col[3]}} {'n/a':<{col[4]}} {'SKIP':<{col[5]}}"
            )
            continue

        wc = rec["word_count"]

        # (a) length check
        length_ok = 50 <= wc <= 300
        if length_ok:
            counts["length"] += 1

        # (b) jargon check
        jargon_flags = _check_jargon(expl)
        jargon_ok = len(jargon_flags) == 0
        if jargon_ok:
            counts["jargon"] += 1

        # (c) med-change language
        med_flags = _check_med_change_language(expl)
        med_ok = len(med_flags) == 0
        if med_ok:
            counts["med_change"] += 1

        # (d) ends with complete sentence
        sentence_ok = expl.strip().endswith((".", "!", "?"))
        if sentence_ok:
            counts["sentence"] += 1

        # (e) fabricated stats (informational — does not affect pass/fail)
        stat_flags = _check_fabricated_stats(expl, ext)

        # Verdict: only (a), (c), (d) are hard gates per final report spec.
        # Jargon and fabricated stats are informational.
        fail_reasons = []
        if not length_ok:
            fail_reasons.append(f"length {wc} outside 50-300")
        if not med_ok:
            fail_reasons.append(f"med-change language: {med_flags}")
        if not sentence_ok:
            fail_reasons.append("explanation ends mid-sentence")

        verdict = "PASS" if not fail_reasons else "FAIL"
        if verdict == "PASS":
            passed += 1
        else:
            issues.extend(f"{fname}: {r}" for r in fail_reasons)

        # Informational notes
        if jargon_flags:
            issues.append(f"{fname}: [info] unexplained jargon: {jargon_flags}")
        if stat_flags:
            issues.append(f"{fname}: [info] possible fabricated stats: {stat_flags}")

        print(
            f"  {fname:<{col[0]}} {'yes' if length_ok else 'NO':<{col[1]}} "
            f"{'yes' if jargon_ok else 'FLAG':<{col[2]}} "
            f"{'yes' if med_ok else 'NO':<{col[3]}} "
            f"{'yes' if sentence_ok else 'NO':<{col[4]}} "
            f"{verdict:<{col[5]}}"
        )

        if jargon_flags:
            print(f"    [jargon info] {jargon_flags}")
        if stat_flags:
            print(f"    [stat info]   {stat_flags}")

    eligible = sum(1 for r in s1_results if not r["error"] and r["response"])
    print(f"\n  Eligible PDFs   : {eligible}")
    print(f"  Length OK       : {counts['length']}/{eligible}")
    print(f"  No jargon flags : {counts['jargon']}/{eligible}")
    print(f"  No med-change   : {counts['med_change']}/{eligible}")
    print(f"  Complete sent.  : {counts['sentence']}/{eligible}")
    print(f"  Overall pass    : {passed}/{eligible}")

    return {
        "passed": passed,
        "total": eligible,
        "issues": issues,
        "counts": counts,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Section 3 — Pipeline resilience with edge-case PDFs
# ──────────────────────────────────────────────────────────────────────────────

# Include enough fields in each PDF so the completeness check does not
# downgrade pipeline_status to "partial" before Agent 2 can run.

_TEXT_3A = """\
Patient: John Smith
Discharge date: 2026-04-01
Diagnosis: Hypertension
Medication: Lisinopril 10mg once daily
Follow up with Dr. Anne Fitzgerald, Primary Care, in 2 weeks.
Call 911 if you have severe chest pain or difficulty breathing.
"""

_TEXT_3B = """\
Patient: Margaret Lee
Discharge date: 2026-04-10
Primary Diagnosis: Acute Decompensated Heart Failure with Reduced Ejection Fraction (HFrEF) secondary to ischemic cardiomyopathy
Medication: Furosemide 40mg once daily
Follow up with Dr. Angela Brooks, Cardiology, on April 26 2026.
Go to the emergency room if you gain more than 2 pounds in one day.
"""

_TEXT_3C_GARBAGE = "@@@@####$$$$%%%%"

_TEXT_3D = """\
Patient: Robert Kim
Discharge date: 2026-04-15
Primary: Type 2 Diabetes Mellitus
Secondary: Hypertension, Hyperlipidemia, Chronic kidney disease Stage 2, Obesity
Medication: Metformin 1000mg twice daily
Follow up with Dr. Lisa Patel, Endocrinology, on May 1 2026.
Go to the ER if your blood sugar is below 60 mg/dL and does not improve.
"""


def run_section_3() -> dict:
    """
    Run 4 resilience edge-case tests using in-memory PDFs built with fpdf2.

    3a — Very short / single-word diagnosis.
         Checks: A1 extracts Hypertension, A2 produces non-empty explanation,
         FK <= 6.0, pipeline_status = "complete".

    3b — Complex multi-word diagnosis with abbreviation.
         Checks: primary_diagnosis contains "heart failure", A2 explanation
         differs from diagnosis string, word count > 30.

    3c — Garbage input ("@@@@####$$$$%%%%").
         Checks: no unhandled exception, pipeline returns a valid response,
         pipeline_status = "partial", Agent 2 did NOT run (explanation empty).

    3d — Multiple secondary diagnoses.
         Checks: all 4 secondary diagnoses extracted, A2 focuses on primary
         diagnosis, word count 50-300.

    Returns:
        dict with keys: passed (int), total (int), issues (list[str]),
        results (list[tuple]), sub_passed (dict[str, bool]).
    """
    print(f"\n{'=' * 70}")
    print("SECTION 3 — Pipeline resilience (4 edge cases)")
    print(f"{'=' * 70}")

    passed = 0
    issues = []
    results = []
    sub_passed = {}

    # ── 3a: Very short diagnosis ──────────────────────────────────────────────
    tmp = _build_pdf(_TEXT_3A)
    try:
        response, error = _run(tmp, "3a_short_diagnosis")
        results.append(("3a_short_diagnosis", response))
        if error:
            issues.append(f"3a: pipeline error — {error}")
            sub_passed["3a"] = False
        else:
            doc_issues = []
            diag = response.extraction.primary_diagnosis or ""
            if "hypertension" not in diag.lower():
                doc_issues.append(
                    f"primary_diagnosis={diag!r} does not contain 'hypertension'"
                )
            if not response.diagnosis_explanation.strip():
                doc_issues.append("Agent 2 explanation is empty")
            fk = response.fk_scores.get("agent2", {})
            if not fk.get("passes", False):
                doc_issues.append(f"FK grade {fk.get('fk_grade')} > 6.0")
            if response.pipeline_status != "complete":
                doc_issues.append(f"pipeline_status={response.pipeline_status!r}, expected 'complete'")

            _print_edge_result("3a", "Short diagnosis: Hypertension", doc_issues, response)
            if doc_issues:
                issues.extend(f"3a: {i}" for i in doc_issues)
                sub_passed["3a"] = False
            else:
                passed += 1
                sub_passed["3a"] = True
    finally:
        os.unlink(tmp)

    # ── 3b: Complex multi-word diagnosis with abbreviation ────────────────────
    tmp = _build_pdf(_TEXT_3B)
    try:
        response, error = _run(tmp, "3b_complex_diagnosis")
        results.append(("3b_complex_diagnosis", response))
        if error:
            issues.append(f"3b: pipeline error — {error}")
            sub_passed["3b"] = False
        else:
            doc_issues = []
            diag = response.extraction.primary_diagnosis or ""
            if "heart failure" not in diag.lower():
                doc_issues.append(
                    f"primary_diagnosis={diag!r} does not contain 'heart failure'"
                )
            expl = response.diagnosis_explanation.strip()
            if expl.lower() == diag.lower():
                doc_issues.append("Agent 2 just repeated the diagnosis verbatim")
            wc = _word_count(expl)
            if wc <= 30:
                doc_issues.append(f"explanation word count {wc} <= 30")

            _print_edge_result("3b", "Complex HFrEF diagnosis", doc_issues, response)
            if doc_issues:
                issues.extend(f"3b: {i}" for i in doc_issues)
                sub_passed["3b"] = False
            else:
                passed += 1
                sub_passed["3b"] = True
    finally:
        os.unlink(tmp)

    # ── 3c: Garbage input — Agent 2 must not run ──────────────────────────────
    tmp = _build_pdf(_TEXT_3C_GARBAGE)
    try:
        response, error = _run(tmp, "3c_garbage_input")
        results.append(("3c_garbage_input", response))
        # A non-None error from _run means the pipeline itself raised — that
        # violates the "never crashes" guarantee.
        if error and response is None:
            issues.append(f"3c: unhandled exception — {error}")
            sub_passed["3c"] = False
        else:
            doc_issues = []
            # If _run returned a response (even from an error fallback), check contract.
            if response is not None:
                if response.pipeline_status != "partial":
                    doc_issues.append(
                        f"expected pipeline_status='partial' on garbage input, "
                        f"got {response.pipeline_status!r}"
                    )
                if response.diagnosis_explanation.strip():
                    doc_issues.append(
                        "Agent 2 produced output on a garbage/partial pipeline — "
                        "should be empty"
                    )
            _print_edge_result("3c", "Garbage input (no crash)", doc_issues, response)
            if doc_issues:
                issues.extend(f"3c: {i}" for i in doc_issues)
                sub_passed["3c"] = False
            else:
                passed += 1
                sub_passed["3c"] = True
    finally:
        os.unlink(tmp)

    # ── 3d: Multiple secondary diagnoses ─────────────────────────────────────
    tmp = _build_pdf(_TEXT_3D)
    try:
        response, error = _run(tmp, "3d_multiple_secondary")
        results.append(("3d_multiple_secondary", response))
        if error:
            issues.append(f"3d: pipeline error — {error}")
            sub_passed["3d"] = False
        else:
            doc_issues = []
            sec = response.extraction.secondary_diagnoses
            if len(sec) < 4:
                doc_issues.append(
                    f"expected 4 secondary diagnoses, got {len(sec)}: {sec}"
                )
            expl = response.diagnosis_explanation.strip()
            diag = response.extraction.primary_diagnosis or ""
            # Primary focus check: explanation should mention diabetes
            if "diabetes" not in expl.lower() and "blood sugar" not in expl.lower():
                doc_issues.append(
                    "Agent 2 explanation does not mention primary diagnosis (diabetes)"
                )
            wc = _word_count(expl)
            if not (50 <= wc <= 300):
                doc_issues.append(f"explanation word count {wc} outside 50-300")

            _print_edge_result("3d", "Multiple secondary diagnoses", doc_issues, response)
            if doc_issues:
                issues.extend(f"3d: {i}" for i in doc_issues)
                sub_passed["3d"] = False
            else:
                passed += 1
                sub_passed["3d"] = True
    finally:
        os.unlink(tmp)

    print(f"\n  Section 3 result: {passed}/4 passed")

    return {
        "passed": passed,
        "total": 4,
        "issues": issues,
        "results": results,
        "sub_passed": sub_passed,
    }


def _print_edge_result(label: str, description: str, doc_issues: list, response) -> None:
    """Print a single Section 3 test result block."""
    verdict = "PASS" if not doc_issues else "FAIL"
    print(f"\n  Test {label} — {description}")
    if response is not None:
        print(f"    pipeline_status     : {response.pipeline_status}")
        print(f"    primary_diagnosis   : {response.extraction.primary_diagnosis or '(none)'}")
        fk = response.fk_scores.get("agent2", {})
        print(f"    fk_grade            : {fk.get('fk_grade', 'n/a')}")
        expl = response.diagnosis_explanation
        if expl.strip():
            print(f"    explanation (first 120): {expl[:120].strip()}")
        else:
            print(f"    explanation         : (empty — Agent 2 did not run)")
    print(f"    VERDICT: {verdict}" + (f" — {'; '.join(doc_issues)}" if doc_issues else ""))


# ──────────────────────────────────────────────────────────────────────────────
# Section 4 — FK score distribution analysis
# ──────────────────────────────────────────────────────────────────────────────

def run_section_4(s1_results: list[dict]) -> dict:
    """
    Analyse the FK score distribution across all 10 Section 1 PDFs.
    Prints best/worst documents and the full text of the highest-scoring
    explanation for manual review. No new LLM calls.

    Args:
        s1_results: Results list from run_section_1().

    Returns:
        dict with keys: avg_fk (float), all_pass (bool), highest (dict),
        issues (list[str]).
    """
    print(f"\n{'=' * 70}")
    print("SECTION 4 — FK score distribution analysis")
    print(f"{'=' * 70}")

    scored = [
        {"filename": r["filename"], "fk_grade": r["fk_grade"], "expl": r["response"].diagnosis_explanation}
        for r in s1_results
        if r["fk_grade"] is not None and r["response"] is not None
    ]

    issues = []

    if not scored:
        print("  No FK scores available (all extractions failed).")
        return {"avg_fk": None, "all_pass": False, "highest": None, "issues": issues}

    grades = [s["fk_grade"] for s in scored]
    avg_fk = sum(grades) / len(grades)
    lowest  = min(scored, key=lambda s: s["fk_grade"])
    highest = max(scored, key=lambda s: s["fk_grade"])

    failures    = [s for s in scored if s["fk_grade"] > 6.0]
    borderline  = [s for s in scored if 5.0 <= s["fk_grade"] <= 6.0]
    good        = [s for s in scored if s["fk_grade"] < 5.0]

    print(f"\n  Lowest FK score  : {lowest['fk_grade']:.1f}  ({lowest['filename']})")
    print(f"  Highest FK score : {highest['fk_grade']:.1f}  ({highest['filename']})")
    print(f"  Average FK score : {avg_fk:.2f}")

    print(f"\n  Scores > 6.0 (failures)    : ", end="")
    if failures:
        print(", ".join(f"{s['filename']} ({s['fk_grade']:.1f})" for s in failures))
        issues.append(f"FK failures: {[s['filename'] for s in failures]}")
    else:
        print("none")

    print(f"  Scores 5.0-6.0 (borderline): ", end="")
    print(", ".join(f"{s['filename']} ({s['fk_grade']:.1f})" for s in borderline) or "none")

    print(f"  Scores < 5.0 (good)        : ", end="")
    print(", ".join(f"{s['filename']} ({s['fk_grade']:.1f})" for s in good) or "none")

    if avg_fk > 5.5:
        issues.append(f"Average FK {avg_fk:.2f} > 5.5 target")

    print(f"\n  === Highest FK explanation — {highest['filename']} (grade {highest['fk_grade']:.1f}) ===")
    print(f"  (Full text for manual review — does this need prompt improvement?)")
    print()
    for line in highest["expl"].splitlines():
        print(f"  {line}")

    all_pass = len(failures) == 0
    return {
        "avg_fk": avg_fk,
        "all_pass": all_pass,
        "highest": highest,
        "issues": issues,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Section 5 — Schema contract verification
# ──────────────────────────────────────────────────────────────────────────────

def run_section_5(
    s1_results: list[dict],
    s3_results: list[tuple],
) -> dict:
    """
    Verify the Agent 1 → Agent 2 → PipelineResponse data contract for every
    response produced in Sections 1 and 3. No new LLM calls.

    Contract checks (see _check_pipeline_contract for full detail):
      a) extraction.primary_diagnosis was Agent 2's input
      b) diagnosis_explanation is a string
      c) fk_scores dict has "agent2" key on complete pipelines
      d) pipeline_status is "complete" or "partial"
      e) No string field is None

    Target: 0 violations.

    Args:
        s1_results: Results from run_section_1().
        s3_results: (label, response) pairs from run_section_3().

    Returns:
        dict with keys: violations (int), issues (list[str]).
    """
    print(f"\n{'=' * 70}")
    print("SECTION 5 — Schema contract verification")
    print(f"{'=' * 70}")

    all_violations = []

    # S1 responses
    for rec in s1_results:
        if rec["response"] is None:
            continue
        v = _check_pipeline_contract(rec["filename"], rec["response"])
        all_violations.extend(v)
        status = "OK" if not v else f"VIOLATIONS: {v}"
        print(f"  {rec['filename']:<28} {status}")

    # S3 responses
    for label, response in s3_results:
        if response is None:
            continue
        v = _check_pipeline_contract(label, response)
        all_violations.extend(v)
        status = "OK" if not v else f"VIOLATIONS: {v}"
        print(f"  {label:<28} {status}")

    print(f"\n  Total contract violations: {len(all_violations)}")
    if all_violations:
        for v in all_violations:
            print(f"    - {v}")

    return {"violations": len(all_violations), "issues": all_violations}


# ──────────────────────────────────────────────────────────────────────────────
# Final report
# ──────────────────────────────────────────────────────────────────────────────

def _print_final_report(
    s1: dict, s2: dict, s3: dict, s4: dict, s5: dict
) -> None:
    """
    Print the combined final report with hard-gate verdicts.

    Hard gates:
      S1: 8/10 minimum overall pass
      S2: 8/10 on length + no med-change language
      S3: 4/4 (no crashes ever)
      S4: average FK <= 5.5
      S5: 0 contract violations

    Args:
        s1-s5: Result dicts from each section runner.
    """
    sub = s3.get("sub_passed", {})
    avg_fk = s4.get("avg_fk")
    highest = s4.get("highest")

    print("\n")
    print("=" * 52)
    print("AGENTS 1 + 2 END-TO-END TEST REPORT")
    print("=" * 52)

    print(f"\nSECTION 1 — Synthetic PDFs ({s1['total']})")
    schema_valid = sum(1 for r in s1["results"] if not r["schema_violations"] and not r["error"])
    fk_passes    = sum(1 for r in s1["results"] if r["fk_passes"])
    complete     = sum(1 for r in s1["results"] if r["response"] and r["response"].pipeline_status == "complete")
    print(f"  Agent 1 schema valid  : {schema_valid}/{s1['total']}")
    print(f"  Agent 2 FK passes     : {fk_passes}/{s1['total']}")
    print(f"  Pipeline complete     : {complete}/{s1['total']}")
    print(f"  Overall pass          : {s1['passed']}/{s1['total']}")

    print(f"\nSECTION 2 — Content quality ({s2['total']} PDFs)")
    c = s2.get("counts", {})
    print(f"  Length OK (50-300 wds): {c.get('length', '?')}/{s2['total']}")
    print(f"  No unexplained jargon : {c.get('jargon', '?')}/{s2['total']}")
    print(f"  No med-change language: {c.get('med_change', '?')}/{s2['total']}")
    print(f"  Complete sentences    : {c.get('sentence', '?')}/{s2['total']}")

    print(f"\nSECTION 3 — Resilience (4 edge cases)")
    print(f"  3a short diagnosis    : {'pass' if sub.get('3a') else 'FAIL'}")
    print(f"  3b complex diagnosis  : {'pass' if sub.get('3b') else 'FAIL'}")
    print(f"  3c partial failure    : {'pass' if sub.get('3c') else 'FAIL'}")
    print(f"  3d multiple secondary : {'pass' if sub.get('3d') else 'FAIL'}")

    print(f"\nSECTION 4 — FK Analysis")
    if avg_fk is not None:
        print(f"  Average FK grade      : {avg_fk:.2f}")
        print(f"  All pass (<= 6.0)     : {'yes' if s4.get('all_pass') else 'no'}")
        if highest:
            print(f"  Highest score PDF     : {highest['filename']} at {highest['fk_grade']:.1f}")
    else:
        print("  (no FK data available)")

    print(f"\nSECTION 5 — Contract violations: {s5['violations']}")

    # ── Hard gate evaluation ──────────────────────────────────────────────────
    gate_s1 = s1["passed"] >= 8
    gate_s2 = (c.get("length", 0) >= 8 and c.get("med_change", 0) >= 8)
    gate_s3 = s3["passed"] == 4
    gate_s4 = avg_fk is not None and avg_fk <= 5.5
    gate_s5 = s5["violations"] == 0

    all_gates = gate_s1 and gate_s2 and gate_s3 and gate_s4 and gate_s5

    print(f"\n  Hard gate checks:")
    print(f"    S1 >= 8/10           : {'PASS' if gate_s1 else 'FAIL'} ({s1['passed']}/{s1['total']})")
    print(f"    S2 length+no-med >=8 : {'PASS' if gate_s2 else 'FAIL'}")
    print(f"    S3 = 4/4             : {'PASS' if gate_s3 else 'FAIL'} ({s3['passed']}/4)")
    fk_str = f"{avg_fk:.2f}" if avg_fk is not None else "n/a"
    print(f"    S4 avg FK <= 5.5     : {'PASS' if gate_s4 else 'FAIL'} ({fk_str})")
    print(f"    S5 = 0 violations    : {'PASS' if gate_s5 else 'FAIL'} ({s5['violations']} violations)")

    print()
    if all_gates:
        print("OVERALL VERDICT:")
        print("  READY FOR AGENT 3 INTEGRATION")
    else:
        print("OVERALL VERDICT:")
        print("  NEEDS FIXES:")
        if not gate_s1:
            print(f"    - S1: only {s1['passed']}/10 pass (need 8)")
        if not gate_s2:
            failing = []
            if c.get("length", 0) < 8:
                print(f"    - S2: length check {c.get('length')}/10 < 8")
            if c.get("med_change", 0) < 8:
                print(f"    - S2: med-change check {c.get('med_change')}/10 < 8")
        if not gate_s3:
            failed = [k for k, v in sub.items() if not v]
            print(f"    - S3: {failed} failed")
        if not gate_s4:
            print(f"    - S4: average FK {fk_str} > 5.5")
        if not gate_s5:
            print(f"    - S5: {s5['violations']} contract violations")

    print("=" * 52)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run all five sections in order, then print the final report.
    Sections 2, 4, and 5 reuse results from Sections 1 and 3 — no extra LLM calls.
    """
    provider   = os.environ.get("LLM_PROVIDER", "openrouter")
    model_name = os.environ.get("LLM_MODEL", "default")
    # S1=10, S3=4 pipeline calls; S2/S4/S5 are pure Python
    total_calls = 10 + 4
    approx_min  = (total_calls * _INTER_CALL_DELAY_SECONDS) // 60

    print("Agents 1 + 2 end-to-end test suite")
    print(f"Provider  : {provider}  |  Model: {model_name}")
    print(f"Delay     : {_INTER_CALL_DELAY_SECONDS}s between calls  "
          f"(approx {approx_min} min wait time for {total_calls} calls)")

    s1 = run_section_1()
    s2 = run_section_2(s1["results"])
    s3 = run_section_3()
    s4 = run_section_4(s1["results"])
    s5 = run_section_5(s1["results"], s3["results"])

    _print_final_report(s1, s2, s3, s4, s5)


if __name__ == "__main__":
    main()
