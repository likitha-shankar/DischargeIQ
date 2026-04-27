"""
File: test-data/stress-test/generate_stress_pdfs.py
Owner: Likitha Shankar
Description: fpdf2 generator for messy_01–04.pdf — narrative-only, table-only, heavy-abbrev,
  and OCR-noise synthetic discharges to torture Agent 1 parsing beyond clean fixtures.
Key functions/classes: _new_pdf, per-fixture builder functions
Edge cases handled:
  - Outputs into test-data/stress-test/; overwrites prior PDFs; no PHI.
Dependencies: fpdf2
Called by: Manual: python test-data/stress-test/generate_stress_pdfs.py
"""

from pathlib import Path

from fpdf import FPDF

_OUT_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _new_pdf(font_size: int = 11) -> FPDF:
    """Return an FPDF instance with Helvetica set and one blank page added."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=font_size)
    return pdf


def _write_line(pdf: FPDF, text: str, line_height: int = 6) -> None:
    """Write a single line of text, always resetting X to the left margin first.

    Resetting X is necessary because table cell operations leave the cursor
    at the end of the last cell; multi_cell(0,...) interprets width=0 as
    'remaining width from current X', which can be zero or negative after a
    full-width table row.
    """
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, line_height, text)


def _write_para(pdf: FPDF, text: str, line_height: int = 6) -> None:
    """Write a paragraph with a trailing blank line."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, line_height, text)
    pdf.ln(3)


# ---------------------------------------------------------------------------
# messy_01: Narrative prose, no section headers
# ---------------------------------------------------------------------------

def generate_messy_01(out_dir: Path) -> None:
    """
    Narrative paragraph format  --  entire discharge written as flowing prose.

    No section headers. Medications buried mid-sentence. Follow-up
    mentioned once at the end without structured formatting.
    Diagnosis: Acute decompensated heart failure (HFrEF).
    """
    pdf = _new_pdf(font_size=11)
    pdf.set_font("Helvetica", "B", 14)
    _write_line(pdf, "Memorial General Hospital  --  Patient Discharge Summary")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)

    paragraphs = [
        "Patient is a 67-year-old male who presented to the emergency department on "
        "March 12, 2024, with a two-day history of worsening shortness of breath, "
        "bilateral lower extremity edema, and orthopnea. He was admitted to the "
        "cardiology service for further evaluation and management.",

        "On admission, physical examination was notable for elevated jugular venous "
        "pressure, bibasilar crackles, and 3+ pitting edema to the knees. "
        "Echocardiogram demonstrated severely reduced left ventricular ejection "
        "fraction at 25%, consistent with a known history of ischemic cardiomyopathy. "
        "BNP was markedly elevated at 3,420 pg/mL. Chest X-ray showed cardiomegaly "
        "and pulmonary vascular congestion.",

        "The patient was treated with intravenous furosemide 80mg twice daily for "
        "three days with good diuretic response, achieving a net fluid removal of "
        "approximately 4.2 liters over the hospitalization. He was transitioned to "
        "oral furosemide 40mg daily prior to discharge. His carvedilol was continued "
        "at 6.25mg twice daily. Lisinopril 5mg daily was added given his reduced "
        "ejection fraction and absence of contraindications. Spironolactone 25mg "
        "daily was also initiated. He was placed on a 2-gram sodium restricted diet "
        "and fluid restriction of 1.5 liters per day.",

        "During the hospitalization the patient underwent coronary angiography which "
        "revealed non-obstructive coronary artery disease. No revascularization was "
        "indicated. Cardiac resynchronization therapy was discussed with the patient "
        "and family given the severely reduced EF; he was referred to electrophysiology "
        "for outpatient evaluation.",

        "The patient was discharged home on March 17, 2024, in stable condition with "
        "supplemental oxygen requirement having resolved. He was instructed to weigh "
        "himself every morning and call the office if he gains more than 3 pounds in "
        "one day or 5 pounds in one week. He should seek emergency care immediately "
        "if he develops sudden worsening shortness of breath, chest pain, or fainting. "
        "Worsening leg swelling should prompt a call to his doctor the same day.",

        "He is to follow up with Dr. Ramesh Patel in the heart failure clinic in "
        "seven to ten days, and with the electrophysiology team within four weeks. "
        "His primary care physician, Dr. Linda Torres, should be notified of this "
        "admission and the medication changes.",

        "Patient verbalized understanding of discharge instructions. He was "
        "accompanied by his daughter at time of discharge.",
    ]

    for para in paragraphs:
        _write_para(pdf, para)

    pdf.output(str(out_dir / "messy_01.pdf"))
    print("  Written: messy_01.pdf")


# ---------------------------------------------------------------------------
# messy_02: Table-only format
# ---------------------------------------------------------------------------

def _table_header(pdf: FPDF, cols: list[tuple[str, int]], fill_color: tuple) -> None:
    """Render a shaded header row for a table."""
    pdf.set_fill_color(*fill_color)
    pdf.set_font("Helvetica", "B", 10)
    for label, width in cols:
        pdf.cell(width, 8, label, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", size=10)


def generate_messy_02(out_dir: Path) -> None:
    """
    Table-only layout  --  no narrative prose, no standard section labels.

    Medications in a 3-column Drug|Dose|Instructions table.
    Follow-ups in a 2-column Provider|Date table.
    Patient info in a key-value mini-table at the top.
    Diagnosis: Right total hip arthroplasty.
    """
    pdf = _new_pdf(font_size=10)
    pdf.set_font("Helvetica", "B", 14)
    _write_line(pdf, "LAKESIDE ORTHOPEDIC CENTER")
    pdf.set_font("Helvetica", "B", 12)
    _write_line(pdf, "Post-Operative Discharge Record")
    pdf.ln(5)

    # ---- Patient info mini-table ----
    pdf.set_font("Helvetica", "B", 10)
    _write_line(pdf, "PATIENT INFORMATION")
    pdf.ln(1)
    info_rows = [
        ("Patient Name:", "Martha Holloway"),
        ("Date of Birth:", "1951-08-04"),
        ("MRN:", "LO-884421"),
        ("Admission Date:", "2024-02-20"),
        ("Discharge Date:", "2024-02-23"),
        ("Procedure:", "Right Total Hip Arthroplasty"),
        ("Attending Surgeon:", "Dr. S. Anand"),
        ("Discharge Condition:", "Good  --  ambulating with walker"),
    ]
    pdf.set_font("Helvetica", size=10)
    for label, value in info_rows:
        pdf.cell(65, 7, label, border=1)
        pdf.cell(125, 7, value, border=1)
        pdf.ln()
    pdf.ln(5)

    # ---- Diagnoses table ----
    pdf.set_font("Helvetica", "B", 10)
    _write_line(pdf, "DIAGNOSES")
    pdf.ln(1)
    _table_header(pdf, [("Primary Diagnosis", 95), ("Secondary Diagnoses", 95)], (200, 200, 200))
    pdf.cell(95, 7, "Severe right hip osteoarthritis (M16.11)", border=1)
    pdf.cell(95, 7, "Essential hypertension, Type 2 DM (controlled)", border=1)
    pdf.ln()
    pdf.ln(5)

    # ---- Medications table ----
    pdf.set_font("Helvetica", "B", 10)
    _write_line(pdf, "DISCHARGE MEDICATIONS")
    pdf.ln(1)
    med_cols = [("DRUG NAME", 65), ("DOSE / ROUTE", 55), ("INSTRUCTIONS", 70)]
    _table_header(pdf, med_cols, (200, 200, 200))

    meds = [
        ("Oxycodone/Acetaminophen", "5mg/325mg PO", "Every 4-6 hrs PRN pain x 5 days"),
        ("Celecoxib", "200mg PO", "Twice daily x 2 weeks"),
        ("Enoxaparin (Lovenox)", "40mg SC", "Once daily x 14 days  --  DVT prophylaxis"),
        ("Pantoprazole", "40mg PO", "Once daily  --  GI protection"),
        ("Metformin", "500mg PO", "Twice daily  --  resume home dose"),
        ("Lisinopril", "10mg PO", "Once daily  --  resume home dose"),
        ("Docusate sodium", "100mg PO", "Twice daily while on opioids"),
    ]
    pdf.set_font("Helvetica", size=9)
    for drug, dose, instructions in meds:
        pdf.cell(65, 7, drug, border=1)
        pdf.cell(55, 7, dose, border=1)
        pdf.cell(70, 7, instructions, border=1)
        pdf.ln()
    pdf.ln(5)

    # ---- Follow-up table ----
    pdf.set_font("Helvetica", "B", 10)
    _write_line(pdf, "SCHEDULED FOLLOW-UP APPOINTMENTS")
    pdf.ln(1)
    fu_cols = [("PROVIDER / CLINIC", 95), ("APPOINTMENT DATE", 50), ("PURPOSE", 45)]
    _table_header(pdf, fu_cols, (200, 200, 200))

    followups = [
        ("Dr. S. Anand  --  Orthopedic Surgery", "2024-03-05", "Wound check"),
        ("Physical Therapy  --  Lakeside Rehab", "2024-02-26", "Gait training"),
        ("Dr. Patel  --  Primary Care", "2024-03-12", "Post-op general review"),
    ]
    pdf.set_font("Helvetica", size=9)
    for provider, date, reason in followups:
        pdf.cell(95, 7, provider, border=1)
        pdf.cell(50, 7, date, border=1)
        pdf.cell(45, 7, reason, border=1)
        pdf.ln()
    pdf.ln(5)

    # ---- Restrictions table ----
    pdf.set_font("Helvetica", "B", 10)
    _write_line(pdf, "RESTRICTIONS & PRECAUTIONS")
    pdf.ln(1)
    _table_header(pdf, [("CATEGORY", 50), ("RESTRICTION", 140)], (200, 200, 200))
    restrictions = [
        ("Activity", "No weight bearing on right leg without walker for 6 weeks"),
        ("Activity", "Hip precautions: no flexion >90 degrees, no crossing legs"),
        ("Activity", "No driving for minimum 4 weeks or while taking opioids"),
        ("Diet", "Low sugar diet  --  diabetic protocol"),
        ("Wound", "Keep incision dry for 48 hours; no submerging in water x 4 wks"),
    ]
    pdf.set_font("Helvetica", size=9)
    for cat, restr in restrictions:
        pdf.cell(50, 7, cat, border=1)
        pdf.cell(140, 7, restr, border=1)
        pdf.ln()

    pdf.output(str(out_dir / "messy_02.pdf"))
    print("  Written: messy_02.pdf")


# ---------------------------------------------------------------------------
# messy_03: Heavy medical abbreviations
# ---------------------------------------------------------------------------

def generate_messy_03(out_dir: Path) -> None:
    """
    Abbreviation-heavy document  --  simulates a rapid clinical handoff note.

    Every section uses medical shorthand: dx, rx, hx, sob, f/u, d/c, qd, bid,
    prn, IM, IV, po, w/, s/p, c/o, r/o, etc.
    Diagnosis: NSTEMI (Non-ST-Elevation Myocardial Infarction).
    """
    pdf = _new_pdf(font_size=11)
    pdf.set_font("Helvetica", "B", 13)
    _write_line(pdf, "RIVERSIDE MEDICAL CTR  --  D/C SUMMARY")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)

    sections = [
        ("PT INFO",
         "Pt: James T. Nguyen  DOB: 03/22/1958  MRN: RMC-20941\n"
         "Adm: 01/08/2024  D/C: 01/12/2024  LOS: 4d\n"
         "Att: Dr. A. Kapoor (Cards)  Unit: CCU-3B"),

        ("CC / HPI",
         "67M c/o acute onset CP x 3hrs, SOB, diaphoresis. Hx CAD s/p "
         "PTCA 2019 (LAD). PMHx: HTN, HLD, T2DM, prev smoker (30pk-yr, quit 2010). "
         "NKDA. EMS brought pt to ED; initial ECG w/ ST depr V4-V6, TWI III/aVF. "
         "Trop I 0.8 -> 4.2 -> 6.1 (serial). Dx: NSTEMI."),

        ("HOSP COURSE",
         "Pt adm CCU. Heparin gtt initiated per ACS protocol. "
         "ASA 325mg load -> 81mg QD. Ticagrelor 180mg load -> 90mg BID. "
         "Atorvastatin uptitrated to 80mg QHS. Metop succinate held x24h, "
         "restarted 25mg QD -> uptitrated 50mg QD HD#2. "
         "Cath HD#2: 90% prox LAD stenosis -> DES placed (TIMI 3 flow post). "
         "No sig dz RCA/LCx. EF 45% (mild reduction) on TTE. "
         "Creat 1.1 stable. HbA1c 8.2%. Gluc managed w/ sliding scale; "
         "home metformin held peri-procedure, resumed HD#3. "
         "Pt tolerated PO, ambulating, O2 sat 97% RA at d/c."),

        ("D/C DX",
         "1. NSTEMI  --  Prox LAD, s/p DES x1\n"
         "2. CAD (known)\n"
         "3. HTN (chronic)\n"
         "4. HLD (chronic)\n"
         "5. T2DM (chronic)"),

        ("D/C MEDS (all PO unless noted)",
         "ASA 81mg QD (lifelong  --  do NOT d/c)\n"
         "Ticagrelor 90mg BID x12mo min  --  do NOT d/c w/o Cards approval\n"
         "Atorvastatin 80mg QHS\n"
         "Metoprolol succinate 50mg QD\n"
         "Lisinopril 5mg QD\n"
         "Metformin 500mg BID (resumed)\n"
         "NTG SL 0.4mg PRN CP  --  call 911 if CP unreleved after 3 doses"),

        ("ACTIVITY / DIET",
         "Activity: light ADLs ok; no strenuous exertion x4wks; no lifting >10lbs\n"
         "Diet: cardiac diet  --  low Na (<2g/d), low sat fat; diabetic diet\n"
         "Driving: no driving x1wk or per Cards clearance"),

        ("RED FLAGS  --  go to ED/call 911",
         "Recurrent CP or pressure at rest\n"
         "SOB at rest or w/ minimal exertion\n"
         "Syncope or near-syncope\n"
         "Bleeding from cath site (groin) not controlled w/ pressure"),

        ("F/U",
         "Cards (Dr. Kapoor)  --  1wk p d/c (01/19/2024)  --  wound chk + stress test sched\n"
         "PCP (Dr. Wu)  --  2wks p d/c  --  BP mgmt, DM f/u\n"
         "Cardiac rehab  --  referral placed, pt to expect call w/in 1wk"),

        ("D/C COND",
         "Stable. Pt + family verbalized understanding. Written instrx provided. "
         "Pt ambulating indep. O2 sat 97% RA."),
    ]

    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 11)
        _write_line(pdf, heading + ":")
        pdf.set_font("Helvetica", size=11)
        _write_para(pdf, body)

    pdf.output(str(out_dir / "messy_03.pdf"))
    print("  Written: messy_03.pdf")


# ---------------------------------------------------------------------------
# messy_04: OCR-style errors
# ---------------------------------------------------------------------------

def generate_messy_04(out_dir: Path) -> None:
    """
    Simulated OCR/scan artefacts  --  text is present but contains character
    substitutions, inconsistent spacing, and garbled words typical of
    low-quality document scanning.

    Errors introduced:
    - rn -> m substitutions (common OCR confusion): "Furosernide", "Metoprclol"
    - 0/O and 1/l confusion: "l0mg", "O.5mg"
    - Run-together words: "bloodpressure", "heartfailure"
    - Extra spaces mid-word: "Lisi n opril", "Sp i r onolactone"
    - Missing spaces after colons/commas
    - Hyphen/dash OCR errors: "fo1low-up" -> "fo1Iow-up"

    Diagnosis: Chronic systolic heart failure with COPD exacerbation.
    """
    pdf = _new_pdf(font_size=11)
    pdf.set_font("Helvetica", "B", 13)
    _write_line(pdf, "NORTHVIEW HEALTHSYSTEMDlSCHARGE SUMMARY")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)

    sections = [
        ("PATIENT INFORMATION",
         "Narne: Dorothy B. Haskell         D0B:  June 4, l947\n"
         "MRN: NV-0029 1 3                   Adrnission Date: February 06,2024\n"
         "Discharge Date: February  1 1,2024  Attending: Dr. M.Okonkwo"),

        ("PRIMARY DIAGNOSIS",
         "Acute exacerbation of Chronic Obstructive Pulrnonary Disease (COPD) "
         "with underlying congestive heartfailure (EF 35%).\n"
         "Secondary: Hypertension, Chronic kidney disease Stage 2,Anemia of "
         "chronic disease."),

        ("HOSPITAL COURSE",
         "76-year-oId fernale presented with worsening shortness of breath and "
         "increased sputum production over 3 days. She was febrile on admission "
         "(T 38.6C).CXR dernonstrated hyperinflation with bilateral lower lobe "
         "infiltrates.WBC 13.2. Procalcitonin 0.8. Sputum culture sent.\n\n"
         "Pt treated with IV rnethylprednisolone 40mg q8h x48h then transitioned "
         "to oral prednisone 40mg daily taper over 5 days. Azithrornycin 500mg "
         "daily x5 days initiated for possible atypical infection.Nebulized "
         "albuterol q4h and ipratropium q6h administered throughout stay. "
         "Oxygen titrated to rnaintain SpO2 >92%.\n\n"
         "For volume overload: IV Furosernide 40mg BID x2d then po Furosernide "
         "20rng daily. Net fluid rernoval 2.1L. Spironolactone 25rng daily "
         "continued. Metoprclol succinate l 2.5rng daily continued. "
         "Lisi n opril l0rng daily continued."),

        ("DISCHARGE MEDICATIONS",
         "1. Furosernide  20 rng  po  daily  (new  dose)\n"
         "2. Sp i r onolactone  25 rng  po  daily\n"
         "3. Metoprclol  succinate  l 2.5 rng  po  daily\n"
         "4. Lisi n opril  l 0 rng  po  daily\n"
         "5. Prednisone  40 rng  po  daily  (taper:  reduce  by  l 0 rng  every  3  days)\n"
         "6. Azithrornycin  250 rng  po  daily  x  3  rnore  days  (cornplete  course)\n"
         "7. Albuterol  inhaler  2  puffs  q4-6h  PRN  shortness  of  breath\n"
         "8. Tiotropiurn  (Spir iva)  l 8 rnc g  inhaled  daily"),

        ("ACTIVITY AND DIETARY RESTRICTIONS",
         "Activity: Restricted to light activity.Avoid strenuous exertion.Use "
         "supplemental O2  at horne as prescribed (2L/rnin via nasal cannula).\n"
         "Diet: 2g sodiurn restricted diet.Fluid restriction l .5 L/day."
         "High calorie, high protein rneal supplements recomrnended."),

        ("WARNING SIGNS - RETURN TO ED IF:",
         "- Shortness of breath at rest or not irnproved with inhaler\n"
         "- O2 saturation bel0w 90% on horne pulse oxirneter\n"
         "- Worsening leg swelling or weight gain >3 lbs in one day\n"
         "- Fever above 38.5C\n"
         "- Increased confusion or unusual drowsiness"),

        ("FO1IOW-UP APPOINTMENTS",
         "1.  Dr. M. Okorn wo  (Pulrnonology/Cards)   --   Feb  18, 2024   --   "
         "post-discharge  review\n"
         "2.  Dr.  R.  Singh  (Prirnary  Care)   --   Feb  21, 2024   --   "
         "rnedication  reconciliation\n"
         "3.  Horne  health  nursing   --   Feb  12, 2024   --   wound  and  "
         "rnedication  cornpliance  check"),

        ("DISCHARGE CONDITION",
         "Stable.O2 sat 93% on 2L NC at tirne of discharge.Arnbulating with "
         "assistance. Patient and daughter educated on horne O2 use, rnedications, "
         "and return precautions."),
    ]

    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 11)
        _write_line(pdf, heading)
        pdf.set_font("Helvetica", size=11)
        _write_para(pdf, body)

    pdf.output(str(out_dir / "messy_04.pdf"))
    print("  Written: messy_04.pdf")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Generating stress-test PDFs in: {_OUT_DIR}")
    generate_messy_01(_OUT_DIR)
    generate_messy_02(_OUT_DIR)
    generate_messy_03(_OUT_DIR)
    generate_messy_04(_OUT_DIR)
    print("Done.")
