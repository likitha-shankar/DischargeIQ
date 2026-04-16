"""
Full regression and robustness test suite for Agent 1 (DIS-5).

Five sections cover every known failure mode and hard-gate criterion:

  S1 — 4 regression PDFs: exact expected field values for previously
       validated documents (Furosemide changed, Enoxaparin new, etc.)

  S2 — 10 synthetic PDFs: 8 structural checks per document.
       Hard gate: 8/10 must pass before Agent 2 development begins.

  S3 — 3 real-world simulation PDFs built in-memory with fpdf2:
       3a prose medications, 3b no section headers + IV->oral route change,
       3c 5-page multi-page NSTEMI document.

  S4 — 5 adversarial inputs: empty PDF, garbage text, single word,
       very short document, and conflicting doses between sections.

  S5 — Schema compliance: verifies every ExtractionOutput produced in S1-S4
       matches the locked contract (field types, valid statuses, etc.).

An 8-second delay is enforced between every LLM call to stay within
free-tier rate limits (~7-8 RPM).

Dependencies (all in requirements.txt):
  fpdf2, pdfplumber, pydantic, python-dotenv, openai

Run:
    python test_agent1_full.py

Requires OPENROUTER_API_KEY (or the configured LLM_PROVIDER key) in .env.
"""

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
from dischargeiq.models.extraction import ExtractionOutput

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_TEST_DATA_DIR = Path(__file__).parent / "test-data"

# Seconds to wait between every LLM call.
_INTER_CALL_DELAY_SECONDS = 8

# Valid medication status values per the locked schema.
_VALID_STATUSES = {"new", "changed", "continued", "discontinued", None}

# Module-level timestamp used to enforce the inter-call delay across all
# sections. Updated inside _extract() immediately after each API call.
_last_call_time: float = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Core extraction helper — never raises
# ──────────────────────────────────────────────────────────────────────────────

def _extract(
    pdf_path: str, label: str
) -> tuple[Optional[ExtractionOutput], Optional[str]]:
    """
    Run the full extraction pipeline on a single PDF, enforcing an 8-second
    inter-call delay. Never raises an exception — returns (result, None) on
    success or (None, error_message) on any failure.

    Args:
        pdf_path: Path to the PDF file to process.
        label:    Short human-readable label printed to stdout.

    Returns:
        (ExtractionOutput, None) on success.
        (None, error_string) on failure.
    """
    global _last_call_time

    # Sleep until 8 seconds have elapsed since the last call.
    elapsed = time.time() - _last_call_time
    if _last_call_time > 0 and elapsed < _INTER_CALL_DELAY_SECONDS:
        sleep_secs = _INTER_CALL_DELAY_SECONDS - elapsed
        print(f"  [rate limit] sleeping {sleep_secs:.1f}s ...", flush=True)
        time.sleep(sleep_secs)

    print(f"  Extracting: {label} ...", end="", flush=True)

    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        result = run_extraction_agent(pdf_text)
        _last_call_time = time.time()
        print(" done")
        return result, None
    except FileNotFoundError as exc:
        _last_call_time = time.time()
        print(" ERROR")
        return None, f"File not found: {exc}"
    except OSError as exc:
        _last_call_time = time.time()
        print(" ERROR")
        return None, f"OS error: {exc}"
    except ValueError as exc:
        # Covers json.JSONDecodeError (subclass of ValueError) and Pydantic parse errors.
        _last_call_time = time.time()
        print(" ERROR")
        return None, f"Parse error: {exc}"
    except Exception as exc:  # noqa: BLE001 — intentional catch-all for robustness tests
        _last_call_time = time.time()
        print(" ERROR")
        return None, f"{type(exc).__name__}: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# Field-level helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_med(medications: list, name_fragment: str):
    """
    Return the first Medication whose name contains name_fragment
    (case-insensitive). Returns None if no match is found.

    Args:
        medications:   List of Medication objects from an ExtractionOutput.
        name_fragment: Substring to search for (e.g. "furosemide").

    Returns:
        The matching Medication object, or None.
    """
    fragment_lower = name_fragment.lower()
    for med in medications:
        if fragment_lower in (med.name or "").lower():
            return med
    return None


def _check_schema(label: str, result: ExtractionOutput) -> list[str]:
    """
    Verify that an ExtractionOutput instance matches the locked schema contract.

    Checks:
    - primary_diagnosis is a non-empty string
    - All list fields are lists (not None or other types)
    - All medications have a non-empty name
    - All medication statuses are from the valid set
    - Follow-up appointments are objects (not primitives)

    Args:
        label:  Document label used as a prefix in violation messages.
        result: Validated ExtractionOutput from run_extraction_agent().

    Returns:
        List of violation strings. Empty list means fully compliant.
    """
    violations = []

    if not isinstance(result.primary_diagnosis, str) or not result.primary_diagnosis.strip():
        violations.append(f"{label}: primary_diagnosis missing or empty")

    for list_field in (
        "secondary_diagnoses",
        "procedures_performed",
        "medications",
        "follow_up_appointments",
        "activity_restrictions",
        "dietary_restrictions",
        "red_flag_symptoms",
        "extraction_warnings",
    ):
        val = getattr(result, list_field)
        if not isinstance(val, list):
            violations.append(
                f"{label}: {list_field} expected list, got {type(val).__name__}"
            )

    for i, med in enumerate(result.medications):
        if not med.name or not med.name.strip():
            violations.append(f"{label}: medications[{i}].name is empty or null")
        if med.status not in _VALID_STATUSES:
            violations.append(
                f"{label}: medication {med.name!r} has invalid status {med.status!r}"
            )

    return violations


# ──────────────────────────────────────────────────────────────────────────────
# PDF builders for Section 3 real-world simulations
# ──────────────────────────────────────────────────────────────────────────────

def _build_single_page_pdf(text: str) -> str:
    """
    Write plain ASCII text to a single-page PDF using fpdf2.
    Returns the path to a temporary file. Caller must delete it.

    Args:
        text: Plain ASCII text to embed (multi-line strings are handled).

    Returns:
        Absolute path to the temporary .pdf file.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    # Pass full text as one call — avoids per-line width-zero errors in fpdf2.
    if text.strip():
        pdf.multi_cell(0, 6, text)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    pdf.output(tmp.name)
    return tmp.name


def _build_multipage_pdf(pages: list[str]) -> str:
    """
    Write a multi-page PDF where each string in pages becomes one page.
    Returns the path to a temporary file. Caller must delete it.

    Args:
        pages: List of plain ASCII strings. One new PDF page per entry.

    Returns:
        Absolute path to the temporary .pdf file.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=11)
    for page_text in pages:
        pdf.add_page()
        if page_text.strip():
            pdf.multi_cell(0, 6, page_text)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    pdf.output(tmp.name)
    return tmp.name


# ──────────────────────────────────────────────────────────────────────────────
# Section 1 — Regression PDFs
# ──────────────────────────────────────────────────────────────────────────────

def run_section_1() -> dict:
    """
    Run exact-value regression checks on 4 previously validated synthetic PDFs.

    Each test checks specific field values that were manually verified to be
    correct after prompt engineering. A document passes only if every check
    for that document passes.

    Checked values:
      heart_failure_01 — Furosemide.status == 'changed', Nutritionist
                         follow-up has provider=None, no extraction_warnings
      hip_replacement_02 — Tramadol is NOT marked 'discontinued',
                           no extraction_warnings
      copd_01           — Prednisone.status == 'changed',
                          Azithromycin.status == 'new',
                          >= 6 procedures, no extraction_warnings
      hip_replacement_01 — Enoxaparin.status == 'new',
                           >= 8 procedures, no extraction_warnings

    Returns:
        dict with keys:
          passed  (int)              — number of documents that passed all checks
          total   (int)              — always 4
          issues  (list[str])        — failure descriptions
          results (list[tuple])      — (label, ExtractionOutput | None) pairs
    """
    print("\n=== SECTION 1: Regression PDFs ===")
    passed = 0
    issues: list[str] = []
    results: list[tuple] = []

    # ── heart_failure_01 ─────────────────────────────────────────────────────
    path = str(_TEST_DATA_DIR / "heart_failure_01.pdf")
    result, error = _extract(path, "heart_failure_01.pdf")
    results.append(("heart_failure_01.pdf", result))

    if error:
        issues.append(f"heart_failure_01: extraction failed — {error}")
    else:
        doc_issues: list[str] = []

        furosemide = _find_med(result.medications, "furosemide")
        if furosemide is None:
            doc_issues.append("Furosemide not found in medications")
        elif furosemide.status != "changed":
            doc_issues.append(
                f"Furosemide.status = {furosemide.status!r}, expected 'changed'"
            )

        # Nutritionist follow-up must exist with provider=None (clinic, not a named doctor).
        nutritionist_appt = next(
            (a for a in result.follow_up_appointments
             if "nutritionist" in (a.specialty or "").lower()),
            None,
        )
        if nutritionist_appt is None:
            doc_issues.append("No follow-up with specialty='Nutritionist' found")
        elif nutritionist_appt.provider is not None:
            doc_issues.append(
                f"Nutritionist follow-up provider should be None, "
                f"got {nutritionist_appt.provider!r}"
            )

        if result.extraction_warnings:
            doc_issues.append(
                f"Expected no extraction_warnings, got: {result.extraction_warnings}"
            )

        if doc_issues:
            issues.extend(f"heart_failure_01: {i}" for i in doc_issues)
        else:
            passed += 1

    # ── hip_replacement_02 ───────────────────────────────────────────────────
    path = str(_TEST_DATA_DIR / "hip_replacement_02.pdf")
    result, error = _extract(path, "hip_replacement_02.pdf")
    results.append(("hip_replacement_02.pdf", result))

    if error:
        issues.append(f"hip_replacement_02: extraction failed — {error}")
    else:
        doc_issues = []

        # Tramadol appears in discharge medications list, so it cannot be 'discontinued'.
        # (A discontinued medication is removed from discharge meds by definition.)
        tramadol = _find_med(result.medications, "tramadol")
        if tramadol is not None and tramadol.status == "discontinued":
            doc_issues.append(
                "Tramadol is in discharge medications but marked 'discontinued' — "
                "a medication in the discharge list cannot be discontinued"
            )

        if result.extraction_warnings:
            doc_issues.append(
                f"Expected no extraction_warnings, got: {result.extraction_warnings}"
            )

        if doc_issues:
            issues.extend(f"hip_replacement_02: {i}" for i in doc_issues)
        else:
            passed += 1

    # ── copd_01 ──────────────────────────────────────────────────────────────
    path = str(_TEST_DATA_DIR / "copd_01.pdf")
    result, error = _extract(path, "copd_01.pdf")
    results.append(("copd_01.pdf", result))

    if error:
        issues.append(f"copd_01: extraction failed — {error}")
    else:
        doc_issues = []

        prednisone = _find_med(result.medications, "prednisone")
        if prednisone is None:
            doc_issues.append("Prednisone not found in medications")
        elif prednisone.status != "changed":
            doc_issues.append(
                f"Prednisone.status = {prednisone.status!r}, expected 'changed' "
                f"(IV methylprednisolone -> oral prednisone is a route+drug change)"
            )

        azithromycin = _find_med(result.medications, "azithromycin")
        if azithromycin is None:
            doc_issues.append("Azithromycin not found in medications")
        elif azithromycin.status != "new":
            doc_issues.append(
                f"Azithromycin.status = {azithromycin.status!r}, expected 'new'"
            )

        proc_count = len(result.procedures_performed)
        if proc_count < 6:
            doc_issues.append(
                f"Expected >= 6 procedures, got {proc_count}"
            )

        if result.extraction_warnings:
            doc_issues.append(
                f"Expected no extraction_warnings, got: {result.extraction_warnings}"
            )

        if doc_issues:
            issues.extend(f"copd_01: {i}" for i in doc_issues)
        else:
            passed += 1

    # ── hip_replacement_01 ───────────────────────────────────────────────────
    path = str(_TEST_DATA_DIR / "hip_replacement_01.pdf")
    result, error = _extract(path, "hip_replacement_01.pdf")
    results.append(("hip_replacement_01.pdf", result))

    if error:
        issues.append(f"hip_replacement_01: extraction failed — {error}")
    else:
        doc_issues = []

        enoxaparin = _find_med(result.medications, "enoxaparin")
        if enoxaparin is None:
            doc_issues.append("Enoxaparin not found in medications")
        elif enoxaparin.status != "new":
            doc_issues.append(
                f"Enoxaparin.status = {enoxaparin.status!r}, expected 'new'"
            )

        proc_count = len(result.procedures_performed)
        if proc_count < 8:
            doc_issues.append(
                f"Expected >= 8 procedures, got {proc_count} "
                f"(must include therapy, OT sessions, monitoring)"
            )

        if result.extraction_warnings:
            doc_issues.append(
                f"Expected no extraction_warnings, got: {result.extraction_warnings}"
            )

        if doc_issues:
            issues.extend(f"hip_replacement_01: {i}" for i in doc_issues)
        else:
            passed += 1

    return {"passed": passed, "total": 4, "issues": issues, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
# Section 2 — 10 Synthetic PDFs (Hard Gate)
# ──────────────────────────────────────────────────────────────────────────────

def run_section_2() -> dict:
    """
    Run 8 structural checks on every PDF in test-data/.

    A document passes only if all 8 checks pass:
      1. primary_diagnosis is a non-empty string
      2. At least one medication extracted
      3. At least one follow-up appointment extracted
      4. All medications have a non-empty name
      5. All medication statuses are from the valid set
      6. Every follow-up has at least one of provider or specialty non-null
      7. At least one procedure extracted
      8. extraction_warnings is a list (not None or another type)

    Hard gate: 8/10 documents must pass for Agent 2 development to begin.

    Returns:
        dict with keys:
          passed  (int)        — documents that passed all 8 checks
          total   (int)        — number of PDFs found in test-data/
          issues  (list[str])  — per-check failure descriptions
          results (list[tuple])
    """
    print("\n=== SECTION 2: 10 Synthetic PDFs (Hard Gate) ===")
    pdf_files = sorted(_TEST_DATA_DIR.glob("*.pdf"))
    passed = 0
    issues: list[str] = []
    results: list[tuple] = []

    for pdf_path in pdf_files:
        result, error = _extract(str(pdf_path), pdf_path.name)
        results.append((pdf_path.name, result))

        if error:
            issues.append(f"{pdf_path.name}: extraction failed — {error}")
            continue

        doc_issues: list[str] = []

        # Check 1: non-empty primary_diagnosis
        if not isinstance(result.primary_diagnosis, str) or not result.primary_diagnosis.strip():
            doc_issues.append("primary_diagnosis missing or empty")

        # Check 2: at least one medication
        if len(result.medications) == 0:
            doc_issues.append("no medications extracted")

        # Check 3: at least one follow-up
        if len(result.follow_up_appointments) == 0:
            doc_issues.append("no follow-up appointments extracted")

        # Check 4: all medication names are non-empty
        for i, med in enumerate(result.medications):
            if not med.name or not med.name.strip():
                doc_issues.append(f"medications[{i}].name is empty or null")

        # Check 5: all medication statuses are valid
        for med in result.medications:
            if med.status not in _VALID_STATUSES:
                doc_issues.append(
                    f"medication {med.name!r} has invalid status {med.status!r}"
                )

        # Check 6: every follow-up has at least one identifier
        for i, appt in enumerate(result.follow_up_appointments):
            if appt.provider is None and appt.specialty is None:
                doc_issues.append(
                    f"follow_up_appointments[{i}] has neither provider nor specialty"
                )

        # Check 7: at least one procedure extracted
        if len(result.procedures_performed) == 0:
            doc_issues.append("no procedures extracted")

        # Check 8: extraction_warnings is a list (not None, not a string)
        if not isinstance(result.extraction_warnings, list):
            doc_issues.append(
                f"extraction_warnings is {type(result.extraction_warnings).__name__}, "
                f"expected list"
            )

        if doc_issues:
            issues.extend(f"{pdf_path.name}: {i}" for i in doc_issues)
        else:
            passed += 1

    return {"passed": passed, "total": len(pdf_files), "issues": issues, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
# Section 3 — Real-World Simulation PDFs
# ──────────────────────────────────────────────────────────────────────────────

# 3a: Medications listed in paragraph form — no bullet points, no list format.
_TEXT_3A_PROSE_MEDS = """\
DISCHARGE SUMMARY
Patient: James Rodriguez
Date of Discharge: April 10, 2026
Primary Diagnosis: Type 2 Diabetes Mellitus

HOSPITAL COURSE
Mr. Rodriguez, a 58-year-old male, was admitted for poorly controlled blood glucose.
An insulin drip was used during the stay to stabilize his levels. He was transitioned
to oral medications before discharge.

The patient was discharged on metformin 1000mg twice daily, glipizide 5mg once daily,
and lisinopril 10mg daily for blood pressure management.

FOLLOW-UP
Please follow up with Dr. Sarah Kim, Endocrinology, in 4 weeks.

WARNING SIGNS - CALL 911 IF YOU EXPERIENCE:
- Severe chest pain or pressure
- Difficulty breathing
- Loss of consciousness
- Blood sugar below 60 mg/dL that does not improve after eating
"""

# 3b: No standard section headers. IV azithromycin inpatient, oral at discharge.
_TEXT_3B_NO_HEADERS = """\
PATIENT: Maria Chen
April 12, 2026

Maria Chen is a 45-year-old female treated for community-acquired pneumonia.

During her stay she received IV azithromycin 500mg daily via infusion for 3 days.

She was sent home with azithromycin 250mg by mouth once daily for 5 more days.
She takes lisinopril 5mg daily for her blood pressure, which she should continue.

She will see Dr. Robert Park, Internal Medicine, on April 26, 2026.

If she develops worsening shortness of breath, fever above 103 degrees Fahrenheit,
or coughs up blood, she should go to the emergency room immediately.
"""

# 3c: 5-page NSTEMI document. Medications on page 4, follow-ups and red flags on page 5.
# Critical test: follow-up and medication data are not on the first page.
_PAGES_3C_MULTIPAGE = [
    """\
DISCHARGE SUMMARY - PAGE 1
Patient: Thomas Wright
Date of Birth: March 8, 1959
Admission Date: April 5, 2026
Discharge Date: April 12, 2026

ATTENDING PHYSICIAN: Dr. Angela Brooks, Cardiology

REASON FOR ADMISSION:
Mr. Wright is a 67-year-old male presenting with acute chest pain and
elevated cardiac troponins. He was diagnosed with Non-ST-Elevation
Myocardial Infarction (NSTEMI).
""",
    """\
PAGE 2 - HOSPITAL COURSE

Mr. Wright was admitted to the cardiac care unit on April 5, 2026.
Continuous cardiac monitoring was maintained throughout the stay.
He was evaluated by the Cardiology service and placed on anticoagulation.

He underwent coronary angiography on April 6, 2026, which revealed 70 percent
stenosis of the left anterior descending artery. A drug-eluting stent was
placed successfully via percutaneous coronary intervention on the same day.
Post-procedure he remained hemodynamically stable.
""",
    """\
PAGE 3 - PROCEDURES PERFORMED

- Coronary angiography (April 6, 2026): 70 percent LAD stenosis identified
- Percutaneous coronary intervention (April 6, 2026): drug-eluting stent to LAD
- Echocardiogram (April 7, 2026): LVEF 45 percent, mild anterior wall hypokinesis
- Chest X-ray (April 5, 2026): no acute pulmonary edema, no pneumothorax
- Continuous cardiac monitoring throughout admission
- Daily labs: serial troponins, CBC, BMP, lipid panel
- Cardiology consult (April 5, 2026)
""",
    """\
PAGE 4 - MEDICATIONS AT DISCHARGE

The following medications are prescribed at discharge:

- Aspirin 81mg - take 1 tablet by mouth once daily - new
- Atorvastatin 80mg - take 1 tablet by mouth at bedtime - new
- Metoprolol succinate 50mg - take 1 tablet by mouth once daily - new
- Clopidogrel 75mg - take 1 tablet by mouth once daily for 12 months - new

IMPORTANT: Do not stop clopidogrel without talking to your cardiologist.
Stopping early increases the risk of the stent clotting.
""",
    """\
PAGE 5 - FOLLOW-UP AND DISCHARGE INSTRUCTIONS

FOLLOW-UP APPOINTMENTS:
- Dr. Angela Brooks, Cardiology - April 26, 2026 - post-MI follow-up and echo
- Primary Care - within 1 week of discharge for medication review

ACTIVITY RESTRICTIONS:
- No heavy lifting over 10 pounds for 2 weeks
- Short daily walks are encouraged, increase distance gradually
- No driving for 1 week or until cleared by cardiologist

EMERGENCY WARNING SIGNS - GO TO THE ER IMMEDIATELY IF YOU HAVE:
- Chest pain, pressure, or tightness
- Sudden shortness of breath at rest
- Irregular heartbeat or palpitations
- Sudden weakness or numbness on one side of the body
- Bleeding that does not stop
""",
]


def run_section_3() -> dict:
    """
    Run 3 real-world simulation tests using in-memory PDFs built with fpdf2.

    3a — Prose medications:
         Medications listed in a paragraph, not a bullet list. Checks that
         metformin, glipizide, and lisinopril are all extracted.

    3b — No section headers:
         Document uses narrative prose instead of labeled sections. IV
         azithromycin inpatient, oral at discharge.
         Checks: azithromycin.status == 'changed', lisinopril.status == 'continued'.

    3c — 5-page multi-page NSTEMI:
         Medications on page 4, follow-ups and red flags on page 5.
         Checks: aspirin, atorvastatin, metoprolol, clopidogrel all extracted;
         at least 1 follow-up appointment found.

    Returns:
        dict with keys:
          passed      (int)        — sub-sections that passed
          total       (int)        — always 3
          issues      (list[str])
          results     (list[tuple])
          sub_passed  (dict)       — label -> bool, used by the report printer
    """
    print("\n=== SECTION 3: Real-World Simulations ===")
    passed = 0
    issues: list[str] = []
    results: list[tuple] = []
    sub_passed: dict[str, bool] = {}

    # ── 3a: Prose medications ────────────────────────────────────────────────
    tmp = _build_single_page_pdf(_TEXT_3A_PROSE_MEDS)
    try:
        result, error = _extract(tmp, "3a_prose_meds")
        results.append(("3a_prose_meds", result))
        if error:
            issues.append(f"3a_prose_meds: extraction failed — {error}")
            sub_passed["3a"] = False
        else:
            doc_issues: list[str] = []
            for drug in ("metformin", "glipizide", "lisinopril"):
                if _find_med(result.medications, drug) is None:
                    doc_issues.append(f"{drug} not found in medications")
            if doc_issues:
                issues.extend(f"3a_prose_meds: {i}" for i in doc_issues)
                sub_passed["3a"] = False
            else:
                passed += 1
                sub_passed["3a"] = True
    finally:
        os.unlink(tmp)

    # ── 3b: No headers, IV -> oral route change ──────────────────────────────
    tmp = _build_single_page_pdf(_TEXT_3B_NO_HEADERS)
    try:
        result, error = _extract(tmp, "3b_no_headers")
        results.append(("3b_no_headers", result))
        if error:
            issues.append(f"3b_no_headers: extraction failed — {error}")
            sub_passed["3b"] = False
        else:
            doc_issues = []

            azithromycin = _find_med(result.medications, "azithromycin")
            if azithromycin is None:
                doc_issues.append("azithromycin not found in medications")
            elif azithromycin.status != "changed":
                doc_issues.append(
                    f"azithromycin.status = {azithromycin.status!r}, expected 'changed' "
                    f"(IV inpatient -> oral discharge is a route change)"
                )

            lisinopril = _find_med(result.medications, "lisinopril")
            if lisinopril is None:
                doc_issues.append("lisinopril not found in medications")
            elif lisinopril.status != "continued":
                doc_issues.append(
                    f"lisinopril.status = {lisinopril.status!r}, expected 'continued' "
                    f"(pre-existing BP medication with no change)"
                )

            if doc_issues:
                issues.extend(f"3b_no_headers: {i}" for i in doc_issues)
                sub_passed["3b"] = False
            else:
                passed += 1
                sub_passed["3b"] = True
    finally:
        os.unlink(tmp)

    # ── 3c: 5-page multi-page NSTEMI ─────────────────────────────────────────
    tmp = _build_multipage_pdf(_PAGES_3C_MULTIPAGE)
    try:
        result, error = _extract(tmp, "3c_multipage_nstemi")
        results.append(("3c_multipage_nstemi", result))
        if error:
            issues.append(f"3c_multipage_nstemi: extraction failed — {error}")
            sub_passed["3c"] = False
        else:
            doc_issues = []

            for drug in ("aspirin", "atorvastatin", "metoprolol", "clopidogrel"):
                if _find_med(result.medications, drug) is None:
                    doc_issues.append(f"{drug} not extracted (located on page 4)")

            if len(result.follow_up_appointments) == 0:
                doc_issues.append(
                    "no follow-up appointments found (located on page 5)"
                )

            if doc_issues:
                issues.extend(f"3c_multipage_nstemi: {i}" for i in doc_issues)
                sub_passed["3c"] = False
            else:
                passed += 1
                sub_passed["3c"] = True
    finally:
        os.unlink(tmp)

    return {
        "passed": passed,
        "total": 3,
        "issues": issues,
        "results": results,
        "sub_passed": sub_passed,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Section 4 — Adversarial Inputs
# ──────────────────────────────────────────────────────────────────────────────

# 4d: Minimal 4-line note — under 200 words, should trigger the short-document warning.
_TEXT_4D_VERY_SHORT = """\
Patient: Jane Doe
Diagnosis: Hypertension
Medication: Lisinopril 10mg daily
Follow up with Dr. Anne Fitzgerald in 2 weeks.
"""

# 4e: Metformin 500mg at admission, 1000mg in the discharge section.
# The extraction must use the discharge section value (1000mg) and
# must add an extraction_warning about conflicting information.
_TEXT_4E_CONFLICTING = """\
DISCHARGE SUMMARY
Patient: Robert Kim
Date of Discharge: April 15, 2026
Primary Diagnosis: Type 2 Diabetes Mellitus

ADMISSION MEDICATIONS:
- Metformin 500mg twice daily

PROCEDURES PERFORMED:
- Blood glucose monitoring
- Diabetes education session

MEDICATIONS AT DISCHARGE:
- Metformin 1000mg twice daily - take by mouth with meals

FOLLOW-UP:
Dr. Lisa Patel, Endocrinology, May 1, 2026

WARNING SIGNS:
- Blood sugar below 60 mg/dL
- Severe nausea or vomiting
"""


def run_section_4() -> dict:
    """
    Run 5 adversarial input tests.

    4a — Empty PDF: no text content. Agent must not crash.
         Pass: _extract() returns without raising (error string is acceptable).

    4b — Garbage text: random ASCII symbols and nonsense tokens.
         Pass: _extract() returns without raising.

    4c — Single word: PDF contains only the word 'hello'.
         Pass: _extract() returns without raising.

    4d — Very short document: 4-line discharge note under 200 words.
         Pass: primary_diagnosis is non-empty AND extraction_warnings
         contains a short-document or incomplete-document warning.

    4e — Conflicting doses: Metformin 500mg in admission section, 1000mg
         at discharge. Pass: extracted dose is 1000mg (discharge wins) AND
         extraction_warnings contains a conflict warning.

    Returns:
        dict with keys:
          passed      (int)
          total       (int)        — always 5
          issues      (list[str])
          results     (list[tuple])
          sub_passed  (dict)       — label -> bool
    """
    print("\n=== SECTION 4: Adversarial Inputs ===")
    passed = 0
    issues: list[str] = []
    results: list[tuple] = []
    sub_passed: dict[str, bool] = {}

    # ── 4a: Empty PDF ─────────────────────────────────────────────────────────
    # Pass criterion: no crash. An error string from _extract() is acceptable
    # because empty documents may legitimately fail schema validation.
    tmp = _build_single_page_pdf("")
    try:
        result, error = _extract(tmp, "4a_empty_pdf")
        results.append(("4a_empty_pdf", result))
        # _extract() never raises, so reaching here always means no crash.
        passed += 1
        sub_passed["4a"] = True
        if error:
            # Non-crash error is acceptable but worth noting.
            issues.append(f"4a_empty_pdf: non-fatal extraction error (acceptable): {error}")
            # Still passed — we only care that it didn't crash.
    finally:
        os.unlink(tmp)

    # ── 4b: Garbage text ──────────────────────────────────────────────────────
    garbage = ("!@#$%^&*()_+{}|:<>? " * 40 + "\n") * 3 + "xkqw zzpv mflb rntj " * 20
    tmp = _build_single_page_pdf(garbage)
    try:
        result, error = _extract(tmp, "4b_garbage_text")
        results.append(("4b_garbage_text", result))
        passed += 1
        sub_passed["4b"] = True
        if error:
            issues.append(f"4b_garbage_text: non-fatal extraction error (acceptable): {error}")
    finally:
        os.unlink(tmp)

    # ── 4c: Single word ───────────────────────────────────────────────────────
    tmp = _build_single_page_pdf("hello")
    try:
        result, error = _extract(tmp, "4c_single_word")
        results.append(("4c_single_word", result))
        passed += 1
        sub_passed["4c"] = True
        if error:
            issues.append(f"4c_single_word: non-fatal extraction error (acceptable): {error}")
    finally:
        os.unlink(tmp)

    # ── 4d: Very short document ───────────────────────────────────────────────
    tmp = _build_single_page_pdf(_TEXT_4D_VERY_SHORT)
    try:
        result, error = _extract(tmp, "4d_very_short")
        results.append(("4d_very_short", result))
        if error:
            issues.append(f"4d_very_short: extraction failed — {error}")
            sub_passed["4d"] = False
        else:
            doc_issues: list[str] = []

            if not result.primary_diagnosis or not result.primary_diagnosis.strip():
                doc_issues.append("primary_diagnosis missing on very short document")

            # The short-document warning must be present for <200-word docs.
            short_warning = any(
                any(kw in w.lower() for kw in ("short", "incomplete", "partial"))
                for w in result.extraction_warnings
            )
            if not short_warning:
                doc_issues.append(
                    "expected a short-document warning in extraction_warnings "
                    "(document is under 200 words)"
                )

            if doc_issues:
                issues.extend(f"4d_very_short: {i}" for i in doc_issues)
                sub_passed["4d"] = False
            else:
                passed += 1
                sub_passed["4d"] = True
    finally:
        os.unlink(tmp)

    # ── 4e: Conflicting doses ─────────────────────────────────────────────────
    tmp = _build_single_page_pdf(_TEXT_4E_CONFLICTING)
    try:
        result, error = _extract(tmp, "4e_conflicting_doses")
        results.append(("4e_conflicting_doses", result))
        if error:
            issues.append(f"4e_conflicting_doses: extraction failed — {error}")
            sub_passed["4e"] = False
        else:
            doc_issues = []

            metformin = _find_med(result.medications, "metformin")
            if metformin is None:
                doc_issues.append("metformin not found in medications")
            elif "1000" not in (metformin.dose or ""):
                doc_issues.append(
                    f"metformin.dose = {metformin.dose!r}, expected '1000mg' "
                    f"(discharge section value must take precedence over admission)"
                )

            # A conflict warning must be present when the same drug appears
            # with different doses in different sections.
            conflict_warning = any(
                "conflict" in w.lower() for w in result.extraction_warnings
            )
            if not conflict_warning:
                doc_issues.append(
                    "expected a conflicting-dose warning in extraction_warnings"
                )

            if doc_issues:
                issues.extend(f"4e_conflicting_doses: {i}" for i in doc_issues)
                sub_passed["4e"] = False
            else:
                passed += 1
                sub_passed["4e"] = True
    finally:
        os.unlink(tmp)

    return {
        "passed": passed,
        "total": 5,
        "issues": issues,
        "results": results,
        "sub_passed": sub_passed,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Section 5 — Schema Compliance
# ──────────────────────────────────────────────────────────────────────────────

def run_section_5(
    all_results: list[tuple[str, Optional[ExtractionOutput]]]
) -> dict:
    """
    Run schema compliance checks on every ExtractionOutput produced in S1–S4.

    Documents that failed extraction (result is None) are skipped — their
    failures were already reported by the relevant section.

    The compliance check uses _check_schema() which validates:
    - primary_diagnosis is a non-empty string
    - All list fields are lists (not None or other types)
    - All medications have non-empty names
    - All medication statuses are from the valid set

    No new API calls are made in this section.

    Args:
        all_results: Concatenated (label, result) pairs from S1 through S4.

    Returns:
        dict with keys:
          passed  (int)
          total   (int)
          issues  (list[str])
          results (list)       — always [] (no new extractions)
    """
    print("\n=== SECTION 5: Schema Compliance ===")
    passed = 0
    total = 0
    issues: list[str] = []

    for label, result in all_results:
        if result is None:
            # Skip — extraction failure already captured in the source section.
            continue
        total += 1
        violations = _check_schema(label, result)
        if violations:
            issues.extend(violations)
        else:
            passed += 1
            print(f"  {label}: schema OK")

    return {"passed": passed, "total": total, "issues": issues, "results": []}


# ──────────────────────────────────────────────────────────────────────────────
# Report printer
# ──────────────────────────────────────────────────────────────────────────────

def _print_report(
    s1: dict, s2: dict, s3: dict, s4: dict, s5: dict
) -> None:
    """
    Print the final test report as a fixed-width table followed by a verdict.

    Args:
        s1: Result dict from run_section_1().
        s2: Result dict from run_section_2().
        s3: Result dict from run_section_3().
        s4: Result dict from run_section_4().
        s5: Result dict from run_section_5().
    """
    # Pull per-sub-section pass flags from the dicts that track them.
    s3_sub = s3.get("sub_passed", {})
    s4_sub = s4.get("sub_passed", {})

    def _score(section: dict) -> str:
        return f"{section['passed']}/{section['total']}"

    def _pf(flag: bool) -> str:
        return "pass" if flag else "FAIL"

    def _issues_for(prefix: str, all_issues: list[str]) -> str:
        """Return the first matching issue, truncated, or 'none'."""
        matching = [i for i in all_issues if i.startswith(prefix)]
        if not matching:
            return "none"
        first = matching[0][len(prefix) + 2:]  # strip "prefix: "
        if len(first) > 45:
            first = first[:42] + "..."
        suffix = f" (+{len(matching) - 1} more)" if len(matching) > 1 else ""
        return first + suffix

    col1, col2, col3, col4 = 8, 26, 8, 50
    divider = f"  {'-' * col1}-+-{'-' * col2}-+-{'-' * col3}-+-{'-' * col4}"

    print(f"\n{'=' * 100}")
    print("  FINAL TEST REPORT")
    print(f"{'=' * 100}")
    print(
        f"  {'Section':<{col1}}   {'What was tested':<{col2}}   "
        f"{'Score':<{col3}}   {'First issue (or none)':<{col4}}"
    )
    print(divider)

    def _row(section_lbl: str, description: str, score_str: str, first_issue: str) -> None:
        print(
            f"  {section_lbl:<{col1}}   {description:<{col2}}   "
            f"{score_str:<{col3}}   {first_issue:<{col4}}"
        )

    # For S1 and S2, show the raw first issue string (truncated).
    def _first_issue(issue_list: list[str]) -> str:
        if not issue_list:
            return "none"
        s = issue_list[0]
        return s[:47] + "..." if len(s) > 50 else s

    _row("1",  "4 regression PDFs",         _score(s1), _first_issue(s1["issues"]))
    _row("2",  "10 synthetic PDFs",          _score(s2), _first_issue(s2["issues"]))
    _row("3a", "Prose medications",          _pf(s3_sub.get("3a", False)), _issues_for("3a_prose_meds", s3["issues"]))
    _row("3b", "No-header + IV->oral",       _pf(s3_sub.get("3b", False)), _issues_for("3b_no_headers", s3["issues"]))
    _row("3c", "5-page multi-page",          _pf(s3_sub.get("3c", False)), _issues_for("3c_multipage_nstemi", s3["issues"]))
    _row("4a", "Empty PDF (no crash)",       _pf(s4_sub.get("4a", False)), _issues_for("4a_empty_pdf", s4["issues"]))
    _row("4b", "Garbage text (no crash)",    _pf(s4_sub.get("4b", False)), _issues_for("4b_garbage_text", s4["issues"]))
    _row("4c", "Single word (no crash)",     _pf(s4_sub.get("4c", False)), _issues_for("4c_single_word", s4["issues"]))
    _row("4d", "Very short document",        _pf(s4_sub.get("4d", False)), _issues_for("4d_very_short", s4["issues"]))
    _row("4e", "Conflicting doses",          _pf(s4_sub.get("4e", False)), _issues_for("4e_conflicting_doses", s4["issues"]))
    _row("5",  "Schema compliance",          _score(s5), s5["issues"][0] if s5["issues"] else "none")

    print(divider)

    # Hard gate verdict.
    hard_gate_ok = s2["passed"] >= 8
    all_issues = s1["issues"] + s2["issues"] + s3["issues"] + s4["issues"] + s5["issues"]
    # Filter 4a/4b/4c non-fatal notes out of the "needs fixes" count.
    blocking_issues = [
        i for i in all_issues
        if not (
            i.startswith(("4a_empty_pdf: non-fatal", "4b_garbage_text: non-fatal",
                          "4c_single_word: non-fatal"))
        )
    ]

    print()
    if hard_gate_ok and not blocking_issues:
        print("  Overall: READY FOR AGENT 2 INTEGRATION")
    elif hard_gate_ok:
        print(
            f"  Overall: READY FOR AGENT 2 INTEGRATION "
            f"(with {len(blocking_issues)} issue(s) — see above)"
        )
    else:
        print(
            f"  Overall: NEEDS FIXES — hard gate not cleared "
            f"({s2['passed']}/10 < 8 required)"
        )
        for issue in blocking_issues[:10]:
            print(f"    - {issue}")
        if len(blocking_issues) > 10:
            print(f"    ... ({len(blocking_issues) - 10} more issues)")

    print(f"{'=' * 100}\n")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run all five test sections in order, then print the final report.
    Section 5 consumes all results from S1–S4; no additional API calls are made.
    """
    provider = os.environ.get("LLM_PROVIDER", "openrouter")
    model_name = os.environ.get("LLM_MODEL", "default")
    total_calls = 4 + 10 + 3 + 5  # S1 + S2 + S3 + S4 LLM calls
    approx_minutes = (total_calls * _INTER_CALL_DELAY_SECONDS) // 60

    print(f"Agent 1 full test suite — {total_calls} LLM calls")
    print(f"Provider : {provider}  |  Model: {model_name}")
    print(f"Delay    : {_INTER_CALL_DELAY_SECONDS}s between calls  "
          f"(approx {approx_minutes} min total wait time)")

    s1 = run_section_1()
    s2 = run_section_2()
    s3 = run_section_3()
    s4 = run_section_4()

    # Section 5 performs schema checks only — no new API calls.
    all_results = s1["results"] + s2["results"] + s3["results"] + s4["results"]
    s5 = run_section_5(all_results)

    _print_report(s1, s2, s3, s4, s5)


if __name__ == "__main__":
    main()
