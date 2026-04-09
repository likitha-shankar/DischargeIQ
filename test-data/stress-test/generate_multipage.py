"""
Generator for multipage_01.pdf — a 3-page heart failure discharge summary.

Uses reportlab so each page has a proper PDF page boundary, giving pdfplumber
a genuine multi-page document to parse.

Page layout:
  Page 1 — Patient info, primary diagnosis, secondary diagnoses, procedures
  Page 2 — Discharge medications (9 drugs), activity restrictions, dietary restrictions
  Page 3 — Follow-up appointments, red flag symptoms, discharge condition, reviewer block

Diagnosis: Acute Decompensated Heart Failure with Reduced Ejection Fraction (HFrEF)
All content is fully synthetic. No real patient data.

Run from the project root:
    python test-data/stress-test/generate_multipage.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_OUT_PATH = Path(__file__).parent / "multipage_01.pdf"

# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

_STYLES = getSampleStyleSheet()

_HEADER_STYLE = ParagraphStyle(
    "SectionHeader",
    parent=_STYLES["Heading2"],
    fontSize=11,
    spaceAfter=4,
    spaceBefore=10,
    textColor=colors.HexColor("#1a1a1a"),
    borderPad=2,
)

_BODY_STYLE = ParagraphStyle(
    "Body",
    parent=_STYLES["Normal"],
    fontSize=10,
    leading=14,
    spaceAfter=4,
)

_LABEL_STYLE = ParagraphStyle(
    "Label",
    parent=_STYLES["Normal"],
    fontSize=10,
    fontName="Helvetica-Bold",
)

_SMALL_STYLE = ParagraphStyle(
    "Small",
    parent=_STYLES["Normal"],
    fontSize=9,
    leading=12,
)

_TABLE_HEADER_STYLE = [
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 9),
    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
    ("TOPPADDING", (0, 0), (-1, 0), 6),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf2f7")]),
    ("FONTSIZE", (0, 1), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 1), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
]


def _hr() -> HRFlowable:
    """Return a thin horizontal rule for visual section separation."""
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e0"), spaceAfter=4)


def _h(text: str) -> Paragraph:
    """Return a section header paragraph."""
    return Paragraph(text, _HEADER_STYLE)


def _p(text: str) -> Paragraph:
    """Return a body paragraph."""
    return Paragraph(text, _BODY_STYLE)


def _kv(label: str, value: str) -> Paragraph:
    """Return a bolded-label + value paragraph."""
    return Paragraph(f"<b>{label}:</b> {value}", _BODY_STYLE)


def _spacer(height: float = 0.1) -> Spacer:
    """Return a vertical spacer of the given height in inches."""
    return Spacer(1, height * inch)


# ---------------------------------------------------------------------------
# Page 1 content: patient info, diagnoses, procedures
# ---------------------------------------------------------------------------

def _page1_content() -> list:
    """
    Return flowables for Page 1.

    Contains: facility header, patient demographics, admission/discharge dates,
    primary diagnosis, secondary diagnoses, procedures performed.
    """
    elements = []

    # ---- Facility header ----
    elements.append(Paragraph(
        "<b>METROPOLITAN HEART & VASCULAR CENTER</b>",
        ParagraphStyle("Title", parent=_STYLES["Title"], fontSize=14, spaceAfter=2),
    ))
    elements.append(Paragraph(
        "INPATIENT DISCHARGE SUMMARY — CONFIDENTIAL",
        ParagraphStyle("Sub", parent=_STYLES["Normal"], fontSize=10,
                       textColor=colors.HexColor("#718096"), spaceAfter=8),
    ))
    elements.append(_hr())

    # ---- Patient demographics table ----
    elements.append(_h("PATIENT INFORMATION"))
    demo_data = [
        ["Patient Name:", "Gerald T. Kaufman", "MRN:", "MHVC-2024-00841"],
        ["Date of Birth:", "July 14, 1949", "Room:", "4-North, Bed 12"],
        ["Admission Date:", "March 10, 2024", "Discharge Date:", "March 17, 2024"],
        ["Attending Physician:", "Dr. Priya Nair, MD", "Service:", "Cardiology"],
        ["Referring Physician:", "Dr. Alan Cho, MD", "Insurance:", "Medicare Part A/B"],
    ]
    demo_table = Table(demo_data, colWidths=[1.4 * inch, 2.5 * inch, 1.4 * inch, 2.2 * inch])
    demo_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
    ]))
    elements.append(demo_table)
    elements.append(_spacer(0.15))

    # ---- Primary diagnosis ----
    elements.append(_h("PRIMARY DIAGNOSIS"))
    elements.append(_p(
        "Acute Decompensated Heart Failure with Reduced Ejection Fraction (HFrEF) — "
        "Left ventricular ejection fraction 22% on echocardiogram (severely reduced). "
        "New York Heart Association (NYHA) Class III at admission."
    ))
    elements.append(_spacer(0.05))

    # ---- Secondary diagnoses ----
    elements.append(_h("SECONDARY DIAGNOSES"))
    secondary = [
        "1. Hypertension (essential, chronic) — suboptimally controlled on admission",
        "2. Type 2 Diabetes Mellitus — HbA1c 7.8% on admission",
        "3. Chronic Kidney Disease, Stage 3a — eGFR 48 mL/min/1.73m²",
        "4. Atrial fibrillation, paroxysmal — rate-controlled",
        "5. Hyperlipidemia — on statin therapy",
        "6. Moderate mitral regurgitation — noted on echocardiogram",
    ]
    for line in secondary:
        elements.append(_p(line))
    elements.append(_spacer(0.05))

    # ---- Procedures performed ----
    elements.append(_h("PROCEDURES PERFORMED DURING HOSPITALIZATION"))
    procedures = [
        "1. Transthoracic echocardiogram (TTE) — March 11, 2024",
        "2. Right heart catheterization — March 12, 2024 (PCWP 28 mmHg, CI 1.7 L/min/m²)",
        "3. 12-lead ECG (serial, daily)",
        "4. Chest X-ray (admission and repeat March 14, 2024)",
        "5. Renal artery duplex ultrasound — March 13, 2024 (no significant stenosis)",
    ]
    for line in procedures:
        elements.append(_p(line))
    elements.append(_spacer(0.1))

    # ---- Hospital course summary ----
    elements.append(_h("HOSPITAL COURSE SUMMARY"))
    elements.append(_p(
        "Mr. Kaufman is a 74-year-old male with known ischemic cardiomyopathy who presented "
        "with a 5-day history of progressive dyspnea on exertion, orthopnea, and bilateral "
        "lower extremity edema. On examination he was in moderate respiratory distress with "
        "elevated JVP, bibasilar crackles, and 3+ pitting edema to the mid-thigh. BNP was "
        "critically elevated at 5,840 pg/mL. He was admitted to the cardiac step-down unit "
        "and treated with aggressive IV diuresis. Over the course of the admission he "
        "achieved net fluid removal of 6.8 liters with significant symptomatic improvement. "
        "He was transitioned to oral diuretics on hospital day 5. Guideline-directed medical "
        "therapy was optimized prior to discharge."
    ))

    return elements


# ---------------------------------------------------------------------------
# Page 2 content: medications, activity restrictions, dietary restrictions
# ---------------------------------------------------------------------------

def _page2_content() -> list:
    """
    Return flowables for Page 2.

    Contains: discharge medication table (9 drugs with dose/frequency/status),
    activity restrictions, dietary restrictions.
    """
    elements = []

    elements.append(Paragraph(
        "METROPOLITAN HEART & VASCULAR CENTER — Discharge Summary (continued) — Page 2",
        _SMALL_STYLE,
    ))
    elements.append(_p("<b>Patient:</b> Gerald T. Kaufman &nbsp;&nbsp; <b>MRN:</b> MHVC-2024-00841"))
    elements.append(_hr())

    # ---- Discharge medications ----
    elements.append(_h("MEDICATIONS AT DISCHARGE"))
    elements.append(_p(
        "<i>Important: Take all medications exactly as prescribed. "
        "Do NOT stop any medication without calling your cardiologist first.</i>"
    ))
    elements.append(_spacer(0.05))

    med_headers = ["MEDICATION", "DOSE", "FREQUENCY", "ROUTE", "STATUS", "NOTES"]
    med_rows = [
        ["Furosemide (Lasix)", "80 mg", "Twice daily", "Oral", "New dose",
         "Increased from 40mg — weigh daily"],
        ["Carvedilol", "12.5 mg", "Twice daily", "Oral", "Continued",
         "Take with food"],
        ["Lisinopril", "10 mg", "Once daily", "Oral", "Continued",
         "Hold if SBP <90"],
        ["Spironolactone", "25 mg", "Once daily", "Oral", "New",
         "Monitor potassium at 1 week"],
        ["Sacubitril/Valsartan\n(Entresto)", "24/26 mg", "Twice daily", "Oral", "New",
         "Do not take with lisinopril — 36hr washout observed"],
        ["Apixaban (Eliquis)", "5 mg", "Twice daily", "Oral", "Continued",
         "For atrial fibrillation"],
        ["Atorvastatin", "80 mg", "Once nightly", "Oral", "Dose increased",
         "Take at bedtime"],
        ["Metformin", "500 mg", "Twice daily", "Oral", "Resumed",
         "Held during hospitalization — restart day 2 post-discharge"],
        ["Potassium chloride", "20 mEq", "Once daily", "Oral", "New",
         "With spironolactone initiation — reassess at follow-up"],
    ]
    med_col_widths = [1.45 * inch, 0.7 * inch, 0.9 * inch, 0.6 * inch, 0.95 * inch, 1.9 * inch]
    med_table = Table([med_headers] + med_rows, colWidths=med_col_widths, repeatRows=1)
    med_table.setStyle(TableStyle(_TABLE_HEADER_STYLE))
    elements.append(med_table)
    elements.append(_spacer(0.15))

    # ---- Activity restrictions ----
    elements.append(_h("ACTIVITY RESTRICTIONS"))
    activity = [
        "<b>Daily weight monitoring:</b> Weigh yourself every morning before eating "
        "and after using the bathroom. Record in your log. Call your doctor if you gain "
        "more than 2 lbs in one day or 5 lbs in one week.",
        "<b>Physical activity:</b> Light activity only (short walks on flat ground, "
        "up to 10 minutes, 2-3 times per day). No strenuous exercise, heavy lifting "
        "(>10 lbs), or yard work for at least 4 weeks.",
        "<b>Driving:</b> Do not drive for 48 hours after discharge. After that, "
        "you may drive short distances if you feel well and are not dizzy.",
        "<b>Fluid intake:</b> Restrict fluids to 1.5 liters (approximately 50 oz) "
        "per day total, including all beverages, soups, and ice cream.",
        "<b>Home oxygen:</b> Use supplemental oxygen at 2L/min via nasal cannula as "
        "needed for shortness of breath at rest. Monitor O2 saturation with home "
        "pulse oximeter. Call if persistently below 92%.",
        "<b>Wound/IV site care:</b> Check IV insertion site daily for redness, "
        "swelling, or drainage for the next 3 days.",
    ]
    for item in activity:
        elements.append(_p(f"• {item}"))
    elements.append(_spacer(0.1))

    # ---- Dietary restrictions ----
    elements.append(_h("DIETARY RESTRICTIONS"))
    dietary = [
        "Sodium restriction: Strict 2-gram (2,000 mg) sodium diet. Read all food labels. "
        "Avoid canned soups, deli meats, fast food, and processed snacks.",
        "Fluid restriction: 1.5 liters per day (see activity restrictions above).",
        "Potassium-rich foods: You are starting spironolactone and potassium supplements. "
        "Avoid additional potassium supplementation unless directed. Limit large portions "
        "of bananas, oranges, and potatoes until potassium is rechecked.",
        "Diabetic diet: Limit simple carbohydrates and sugars consistent with your "
        "Type 2 Diabetes management plan. Refer to prior nutritionist guidance.",
        "Alcohol: Avoid alcohol completely — it weakens heart muscle and interacts "
        "with your medications.",
    ]
    for item in dietary:
        elements.append(_p(f"• {item}"))

    return elements


# ---------------------------------------------------------------------------
# Page 3 content: follow-up, red flags, discharge condition, reviewer block
# ---------------------------------------------------------------------------

def _page3_content() -> list:
    """
    Return flowables for Page 3.

    Contains: follow-up appointments table, red flag symptoms (three-tier),
    discharge condition, and reviewer/attestation block.
    """
    elements = []

    elements.append(Paragraph(
        "METROPOLITAN HEART & VASCULAR CENTER — Discharge Summary (continued) — Page 3",
        _SMALL_STYLE,
    ))
    elements.append(_p("<b>Patient:</b> Gerald T. Kaufman &nbsp;&nbsp; <b>MRN:</b> MHVC-2024-00841"))
    elements.append(_hr())

    # ---- Follow-up appointments ----
    elements.append(_h("FOLLOW-UP APPOINTMENTS"))
    elements.append(_p(
        "<b>Critical:</b> Attendance at the heart failure clinic visit within 7 days "
        "is mandatory. Missing this appointment increases readmission risk significantly."
    ))
    elements.append(_spacer(0.05))

    fu_headers = ["PROVIDER", "CLINIC / SPECIALTY", "DATE", "PURPOSE"]
    fu_rows = [
        ["Dr. Priya Nair, MD",
         "Heart Failure Clinic",
         "March 24, 2024",
         "Post-discharge weight, BMP, medication titration"],
        ["Dr. Priya Nair, MD",
         "Cardiology",
         "April 14, 2024",
         "Repeat echocardiogram, Entresto titration"],
        ["Dr. Alan Cho, MD",
         "Primary Care",
         "March 27, 2024",
         "Medication reconciliation, blood pressure, diabetes management"],
        ["Cardiac Rehabilitation Program",
         "Cardiac Rehab",
         "April 1, 2024",
         "Initial evaluation — referral placed, patient will receive call"],
        ["Renal / Nephrology",
         "Nephrology",
         "April 7, 2024",
         "CKD monitoring, electrolytes, assess diuretic regimen"],
    ]
    fu_col_widths = [1.5 * inch, 1.5 * inch, 1.3 * inch, 3.2 * inch]
    fu_table = Table([fu_headers] + fu_rows, colWidths=fu_col_widths, repeatRows=1)
    fu_table.setStyle(TableStyle(_TABLE_HEADER_STYLE))
    elements.append(fu_table)
    elements.append(_spacer(0.15))

    # ---- Red flag symptoms ----
    elements.append(_h("WARNING SIGNS — WHEN TO SEEK HELP"))

    elements.append(_p("<b>Call 911 or go to the Emergency Room immediately if:</b>"))
    er_flags = [
        "Sudden severe shortness of breath or inability to breathe lying flat",
        "Chest pain, pressure, tightness, or pain radiating to jaw or left arm",
        "Fainting or loss of consciousness",
        "Heart racing faster than 150 beats per minute with dizziness",
        "O2 saturation below 88% on home pulse oximeter despite oxygen use",
        "Sudden confusion or inability to speak or understand",
    ]
    for flag in er_flags:
        elements.append(_p(f"<font color='red'>&#9679;</font> {flag}"))
    elements.append(_spacer(0.08))

    elements.append(_p("<b>Call your cardiologist (Dr. Nair) the same day if:</b>"))
    same_day = [
        "Weight gain of more than 2 lbs since yesterday or 5 lbs since last week",
        "Increasing leg, ankle, or abdominal swelling",
        "New or worsening shortness of breath with light activity or rest",
        "Dizziness or lightheadedness when standing",
        "Heart rate consistently below 50 or above 100 beats per minute",
        "Blood pressure consistently above 160/100 or below 90/60 mmHg",
        "Potassium supplement side effects: muscle weakness, irregular heartbeat",
    ]
    for flag in same_day:
        elements.append(_p(f"• {flag}"))
    elements.append(_spacer(0.08))

    elements.append(_p("<b>Mention at your next scheduled visit:</b>"))
    next_visit = [
        "Mild ankle swelling that resolves with leg elevation",
        "Occasional mild dizziness that clears quickly on standing",
        "Changes in appetite or energy level",
        "Any new over-the-counter medications or supplements started",
    ]
    for flag in next_visit:
        elements.append(_p(f"• {flag}"))
    elements.append(_spacer(0.1))

    # ---- Discharge condition ----
    elements.append(_h("DISCHARGE CONDITION AND STATUS"))
    elements.append(_p(
        "Mr. Kaufman was discharged home in stable condition on March 17, 2024. "
        "At time of discharge: blood pressure 118/72 mmHg, heart rate 68 bpm (regular), "
        "oxygen saturation 95% on room air, respiratory rate 16 breaths/minute, "
        "afebrile. Bilateral lower extremity edema reduced from 3+ to trace. "
        "Patient was ambulatory and comfortable. He verbalized understanding of "
        "all discharge instructions, medication changes, fluid/sodium restrictions, "
        "daily weight monitoring, and return precautions. Written materials provided "
        "in English and Spanish. Daughter present and instructed as caregiver."
    ))
    elements.append(_spacer(0.12))

    # ---- Reviewer / attestation block ----
    elements.append(_hr())
    elements.append(_h("REVIEWED AND ATTESTED BY"))
    reviewer_data = [
        ["Attending Physician:", "Dr. Priya Nair, MD — Cardiology", "Date:", "March 17, 2024"],
        ["Resident:", "Dr. Samuel Osei, MD (PGY-3)", "Time:", "14:35"],
        ["Pharmacist Review:", "M. Tanaka, PharmD", "Date:", "March 17, 2024"],
        ["Case Manager:", "R. Delgado, MSW", "Date:", "March 17, 2024"],
    ]
    rev_table = Table(reviewer_data, colWidths=[1.4 * inch, 2.8 * inch, 0.7 * inch, 2.6 * inch])
    rev_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
    ]))
    elements.append(rev_table)
    elements.append(_spacer(0.1))
    elements.append(_p(
        "<font size='8' color='#718096'>"
        "This document is confidential and intended solely for the named patient "
        "and authorized healthcare providers. Metropolitan Heart &amp; Vascular Center. "
        "Form MHVC-DC-2024 Rev. 3."
        "</font>"
    ))

    return elements


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_multipage_pdf(out_path: Path) -> None:
    """
    Assemble all three pages into a single PDF using reportlab SimpleDocTemplate.

    Each page's content is separated by a PageBreak so pdfplumber will see
    distinct page objects when iterating pdf.pages.

    Args:
        out_path: Destination path for the generated PDF file.
    """
    from reportlab.platypus import PageBreak

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = (
        _page1_content()
        + [PageBreak()]
        + _page2_content()
        + [PageBreak()]
        + _page3_content()
    )

    doc.build(story)
    print(f"  Written: {out_path.name}  ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    out_dir = Path(__file__).parent
    print(f"Generating multipage discharge PDF in: {out_dir}")
    generate_multipage_pdf(out_dir / "multipage_01.pdf")
    print("Done.")
