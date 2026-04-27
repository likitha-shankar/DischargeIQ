"""
File: scripts/stress/generate_stress_fixtures.py
Owner: Likitha Shankar
Description: ReportLab generator for fixtures 9–14 — Epic/Cerner/Word-like layouts,
  two-column MI narrative, pediatric appendix story, and multipage sepsis distractor —
  written to dischargeiq/tests/fixtures for pipeline stress testing.
Key functions/classes: build_* PDF builder functions (module level)
Edge cases handled:
  - Overwrites existing PDFs idempotently; pure local generation (no API calls).
Dependencies: reportlab; writes under dischargeiq/tests/fixtures
Called by: Developers manually or CI prep: python scripts/stress/generate_stress_fixtures.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = _REPO_ROOT / "dischargeiq" / "tests" / "fixtures"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Shared style helpers ─────────────────────────────────────────────────────

def _styles():
    """Return a paragraph-style dict reused across fixtures."""
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=base["BodyText"], fontSize=10, leading=13
    )
    body_small = ParagraphStyle(
        "body_small", parent=body, fontSize=9, leading=11
    )
    heading = ParagraphStyle(
        "heading", parent=base["Heading2"],
        fontSize=12, leading=14, spaceAfter=4, spaceBefore=6,
    )
    title = ParagraphStyle(
        "title", parent=base["Title"],
        fontSize=14, leading=16, alignment=TA_CENTER, spaceAfter=6,
    )
    subtitle = ParagraphStyle(
        "subtitle", parent=body, fontSize=11, alignment=TA_CENTER,
        spaceAfter=6,
    )
    bold = ParagraphStyle("bold", parent=body, fontSize=10, leading=13)
    return {
        "body": body, "body_small": body_small, "heading": heading,
        "title": title, "subtitle": subtitle, "bold": bold,
        "left": ParagraphStyle("left", parent=body, alignment=TA_LEFT),
    }


# ── Fixture 9: Epic-style CHF After Visit Summary ────────────────────────────

def build_fixture_09() -> Path:
    """Epic AVS layout: patient table, care team, diagnoses w/ ICD-10,
    4-column med table, stopped meds, calendar follow-ups."""
    out = OUT_DIR / "fixture_09_epic_chf.pdf"
    s = _styles()
    doc = SimpleDocTemplate(
        str(out), pagesize=LETTER,
        leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48,
    )
    story = []

    story.append(Paragraph("SAINT ELIZABETH REGIONAL MEDICAL CENTER", s["title"]))
    story.append(Paragraph("[hospital logo]", s["subtitle"]))
    story.append(Paragraph("AFTER VISIT SUMMARY", s["title"]))
    story.append(Spacer(1, 8))

    info = [
        ["Patient:",      "Margaret J. O'Brien",
         "DOB:",          "1951-08-23"],
        ["MRN:",          "00128845",
         "Visit Date:",   "2026-04-14"],
    ]
    tbl = Table(info, colWidths=[0.9 * inch, 2.4 * inch, 0.9 * inch, 1.6 * inch])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))

    story.append(Paragraph("YOUR CARE TEAM", s["heading"]))
    story.append(Paragraph(
        "Attending: Dr. Ravi Patel, MD — Cardiology — (312) 555-0170<br/>"
        "Hospitalist: Dr. Nina Alvarez, MD — Internal Medicine — (312) 555-0188<br/>"
        "Care Coordinator: Angela Barnes, RN — (312) 555-0192",
        s["body"],
    ))

    story.append(Paragraph("WHAT HAPPENED DURING YOUR VISIT", s["heading"]))
    story.append(Paragraph(
        "You came to the hospital with worsening shortness of breath, "
        "swelling in your legs, and weight gain of 8 lbs over one week. "
        "Tests showed that your heart was not pumping as well as it should. "
        "We gave you IV medicine to remove extra fluid from your body. "
        "Over 5 days you felt better, your breathing improved, and your "
        "weight dropped back to baseline. We are sending you home with "
        "new medicines to help your heart pump better.",
        s["body"],
    ))

    story.append(Paragraph("YOUR DISCHARGE DIAGNOSES", s["heading"]))
    story.append(Paragraph(
        "1. Heart failure with reduced ejection fraction (I50.20)<br/>"
        "2. Hypertensive heart disease (I11.9)<br/>"
        "3. Chronic kidney disease, Stage 3a (N18.31)<br/>"
        "4. Type 2 diabetes mellitus (E11.9)",
        s["body"],
    ))

    story.append(Paragraph(
        "MEDICATIONS — PLEASE TAKE THESE MEDICINES", s["heading"]))
    med_rows = [
        ["Medication", "Dose", "How often", "Why you take it"],
        ["Furosemide (Lasix)", "40 mg", "Once daily in morning",
         "Remove extra fluid from body"],
        ["Carvedilol", "6.25 mg", "Twice daily with food",
         "Helps heart pump better"],
        ["Lisinopril", "5 mg", "Once daily",
         "Lowers blood pressure, protects heart"],
        ["Spironolactone", "25 mg", "Once daily",
         "Helps heart, protects kidneys"],
        ["Atorvastatin", "40 mg", "Once daily at bedtime",
         "Lowers cholesterol"],
    ]
    med_tbl = Table(
        med_rows,
        colWidths=[1.7 * inch, 0.9 * inch, 1.5 * inch, 2.4 * inch],
    )
    med_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94A3B8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(med_tbl)
    story.append(Spacer(1, 8))

    story.append(Paragraph("MEDICINES TO STOP TAKING", s["heading"]))
    story.append(Paragraph(
        "Metformin 1000 mg — STOP taking this medicine. "
        "Reason: Hold until kidney function improves. "
        "Dr. Patel will decide when to restart.",
        s["body"],
    ))

    story.append(Paragraph("FOLLOW-UP APPOINTMENTS", s["heading"]))
    appt_rows = [
        ["Date", "Time", "Provider", "Location", "Phone"],
        ["2026-04-21", "9:30 AM",
         "Dr. Ravi Patel (Cardiology)",
         "Saint Elizabeth Clinic, Suite 412",
         "(312) 555-0170"],
        ["2026-04-28", "2:00 PM",
         "Dr. Linda Okafor (Primary Care)",
         "Family Medicine Building, Rm 230",
         "(312) 555-0145"],
        ["2026-05-05", "10:15 AM",
         "Dr. Grace Huang (Nephrology)",
         "Kidney Center, 3rd Floor",
         "(312) 555-0199"],
    ]
    appt_tbl = Table(
        appt_rows,
        colWidths=[0.9 * inch, 0.7 * inch, 2.0 * inch, 2.0 * inch, 0.9 * inch],
    )
    appt_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94A3B8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(appt_tbl)
    story.append(Spacer(1, 8))

    story.append(Paragraph("WHEN TO CALL OR GO TO THE ER", s["heading"]))
    story.append(Paragraph(
        "• Shortness of breath that gets worse or wakes you at night<br/>"
        "• Weight gain of 3 lbs or more in 1 day or 5 lbs in 1 week<br/>"
        "• New or worsening swelling in legs, ankles, or belly<br/>"
        "• Chest pain or pressure that does not go away<br/>"
        "• Fainting, severe dizziness, or a new irregular heartbeat<br/>"
        "• Fever above 101°F (38.3°C)",
        s["body"],
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "If you have questions call (312) 555-0170.",
        s["body_small"],
    ))

    doc.build(story)
    return out


# ── Fixture 10: Cerner-style dense narrative (pneumonia, elderly) ───────────

def build_fixture_10() -> Path:
    """Cerner-style prose — minimal headers, physician-written."""
    out = OUT_DIR / "fixture_10_cerner_pneumonia.pdf"
    s = _styles()
    doc = SimpleDocTemplate(
        str(out), pagesize=LETTER,
        leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
    )
    story = []

    story.append(Paragraph("DISCHARGE SUMMARY", s["title"]))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "Patient: Dorothea Mae Winters, 78F, MRN 4492817<br/>"
        "Admission: 03/12/2026  Discharge: 03/19/2026<br/>"
        "Attending: Dr. Samuel Okonkwo, MD, Internal Medicine",
        s["body"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "PRINCIPAL DIAGNOSIS: Community acquired pneumonia, right lower "
        "lobe, confirmed by chest radiograph 03/12/2026.",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "HOSPITAL COURSE: Mrs. Winters presented to the ED with 4 days of "
        "productive cough, fever to 38.9C, and dyspnea on exertion. CXR "
        "demonstrated right lower lobe infiltrate. She was started on IV "
        "Ceftriaxone 1g Q24H and Azithromycin 500mg QD, transitioned to PO "
        "on hospital day 3 when afebrile x48 hours. Blood cultures x2 NGTD. "
        "SpO2 improved from 91% on admission to 96% on RA at discharge.",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "PMH: HTN, T2DM, CKD stage 2, GERD, Osteoporosis", s["body"]))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "DISCHARGE MEDICATIONS:<br/>"
        "Azithromycin 500mg PO QD x3 more days (complete course)<br/>"
        "Lisinopril 10mg PO QD (home medication, continued)<br/>"
        "Metformin 500mg PO BID (home medication, continued)<br/>"
        "Omeprazole 20mg PO QD AC (home medication, continued)<br/>"
        "Calcium + Vit D 600mg/400IU PO BID (home medication, continued)",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "ALLERGIES: Penicillin (rash), Sulfa drugs", s["body"]))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "FOLLOW UP: PCP Dr. Linda Marsh within 1 week. Repeat CXR in 6 "
        "weeks to confirm resolution. Call office at 312-555-0182.",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "RETURN TO ED IF: fever returns above 38.5C, worsening shortness "
        "of breath, confusion, inability to keep fluids down.",
        s["body"],
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Electronically signed: Dr. Samuel Okonkwo 03/19/2026 14:32",
        s["body_small"],
    ))

    doc.build(story)
    return out


# ── Fixture 11: Word-to-PDF community hospital (knee replacement) ───────────

def build_fixture_11() -> Path:
    """Inconsistent Word formatting — labels with colons, typos, abbrevs."""
    out = OUT_DIR / "fixture_11_word_knee.pdf"
    s = _styles()

    # Slightly different fonts to mimic inconsistent Word formatting
    label = ParagraphStyle(
        "label", parent=s["body"], fontSize=11, leading=14,
        fontName="Helvetica-Bold",
    )
    varied = ParagraphStyle(
        "varied", parent=s["body"], fontSize=10, leading=13,
    )
    smaller = ParagraphStyle(
        "smaller", parent=s["body"], fontSize=9, leading=11,
    )

    doc = SimpleDocTemplate(
        str(out), pagesize=LETTER,
        leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
    )
    story = []

    story.append(Paragraph(
        "LAKESIDE COMMUNITY HOSPITAL — Discharge Instructions", label))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "Patient: Ronald Becker   DOB: 04-18-1958   Discharge Date: 04-12-2026",
        varied,
    ))
    story.append(Paragraph(
        "Surgeon: Dr. Michael Chen, MD, Orthopedic Surgery", smaller))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Procedure:", label))
    story.append(Paragraph(
        "Pt underwent right total knee replacement (arthroplasty) on "
        "04-10-2026 for severe osteoarthritis. Surgery was uncomplicated, "
        "approx 90 minutes. Pt tolerated procedure well.",
        varied,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Diagnosis:", label))
    story.append(Paragraph(
        "Osteoarthritis right knee, s/p total knee arthroplasty. "
        "Other: HTN, Hyperlipidemia",
        varied,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Medications:", label))
    story.append(Paragraph(
        "Percocet 5/325 q4-6h PRN pain (oxycodone/acetaminophen)<br/>"
        "Aspirin 81mg daily for blood clot prevention<br/>"
        "Celebrex 200mg once daily w/ food<br/>"
        "Colace 100mg BID to prevent constipation",
        varied,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Activity:", label))
    story.append(Paragraph(
        "Weight bearing as tolerated w/ walker. Ice knee 20 min on/40 min "
        "off for first 3 days. Elevate leg when sitting. No driving until "
        "off narcotics & approved by surgeon.",
        varied,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Follow-up:", label))
    story.append(Paragraph(
        "f/u w/ Dr. Chen ortho 2wks, call 847-555-0134 to schedule.<br/>"
        "Start outpatient PT approx 1 wk after discharge.",
        varied,
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Warning signs:", label))
    story.append(Paragraph(
        "Go to ER or call 911 for: chest pain, leg swelling/redness "
        "(possible blood clot), fever over 101.5, wound that looks "
        "infected (red, warm, draining), sudden SOB.",
        varied,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Signed: Dr. Michael Chen MD   Date: 04-12-2026", smaller))

    doc.build(story)
    return out


# ── Fixture 12: real two-column platypus frame layout (post-MI) ─────────────

def build_fixture_12() -> Path:
    """Two-column platypus frames — left col fills first, then right."""
    out = OUT_DIR / "fixture_12_twocolumn_mi.pdf"
    s = _styles()

    page_w, page_h = LETTER
    margin = 48
    gutter = 18
    col_w = (page_w - 2 * margin - gutter) / 2
    col_h = page_h - 2 * margin - 40  # leave room for header

    frame_l = Frame(margin, margin, col_w, col_h, id="left",
                    leftPadding=0, rightPadding=0,
                    topPadding=0, bottomPadding=0)
    frame_r = Frame(margin + col_w + gutter, margin, col_w, col_h, id="right",
                    leftPadding=0, rightPadding=0,
                    topPadding=0, bottomPadding=0)

    def on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawCentredString(
            page_w / 2, page_h - margin,
            "MIDTOWN HEART HOSPITAL — Post-MI Discharge Instructions",
        )
        canvas.setFont("Helvetica", 9)
        canvas.drawCentredString(
            page_w / 2, page_h - margin - 14,
            "Patient: James Alvarado   DOB: 1967-03-02   "
            "Discharge: 2026-04-15   Attending: Dr. Neha Rao, Cardiology",
        )
        canvas.restoreState()

    doc = BaseDocTemplate(
        str(out), pagesize=LETTER,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin + 40, bottomMargin=margin,
    )
    doc.addPageTemplates([
        PageTemplate(id="two_col", frames=[frame_l, frame_r],
                     onPage=on_page),
    ])

    story = []

    # ── LEFT COLUMN ──────────────────────────────────────────────────────────
    story.append(Paragraph("YOUR DIAGNOSES", s["heading"]))
    story.append(Paragraph(
        "• Acute MI, anterior wall (STEMI)<br/>"
        "• Coronary artery disease, 3-vessel<br/>"
        "• Hyperlipidemia",
        s["body"],
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("YOUR NEW MEDICATIONS", s["heading"]))
    story.append(Paragraph(
        "Aspirin 81mg — once daily — lifelong<br/>"
        "Clopidogrel 75mg — once daily — 12 months<br/>"
        "Metoprolol succinate 25mg — once daily<br/>"
        "Atorvastatin 80mg — once daily at bedtime<br/>"
        "Lisinopril 5mg — once daily<br/>"
        "Nitroglycerin 0.4mg SL — as needed for chest pain",
        s["body"],
    ))

    # Force the right column to start here
    from reportlab.platypus import FrameBreak
    story.append(FrameBreak())

    # ── RIGHT COLUMN ─────────────────────────────────────────────────────────
    story.append(Paragraph("FOLLOW-UP APPOINTMENTS", s["heading"]))
    story.append(Paragraph(
        "Cardiology: Dr. Patel — April 2, 2026<br/>"
        "Primary Care: Dr. Kim — April 5, 2026<br/>"
        "Cardiac Rehab: Starting April 8, 2026",
        s["body"],
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("CALL 911 IMMEDIATELY IF:", s["heading"]))
    story.append(Paragraph(
        "• Chest pain not relieved by nitro in 5 min<br/>"
        "• Sudden shortness of breath<br/>"
        "• Loss of consciousness<br/>"
        "• Left arm or jaw pain",
        s["body"],
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("ACTIVITY RESTRICTIONS", s["heading"]))
    story.append(Paragraph(
        "• No driving for 1 week<br/>"
        "• No lifting over 10 lbs for 4 weeks<br/>"
        "• Cardiac rehab starts next week",
        s["body"],
    ))

    doc.build(story)
    return out


# ── Fixture 13: Pediatric discharge (parent-directed, appendectomy) ─────────

def build_fixture_13() -> Path:
    """Letter-form instructions addressed to the parent."""
    out = OUT_DIR / "fixture_13_pediatric_appy.pdf"
    s = _styles()
    doc = SimpleDocTemplate(
        str(out), pagesize=LETTER,
        leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
    )
    story = []

    story.append(Paragraph(
        "CHILDREN'S HOSPITAL OF CHICAGO — Pediatric Discharge Instructions",
        s["title"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "Dear Parent/Guardian of Liam Torres (DOB: 06/14/2017):",
        s["bold"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "Your child was admitted for acute appendicitis and underwent "
        "laparoscopic appendectomy on 04/10/2026. The surgery went well "
        "with no complications.",
        s["body"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("PAIN MANAGEMENT:", s["heading"]))
    story.append(Paragraph(
        "Give Ibuprofen 200mg (1 tablet) by mouth every 6 hours WITH FOOD "
        "for pain. If pain is not controlled, you may also give "
        "Acetaminophen 325mg every 6 hours, alternating with Ibuprofen. "
        "Do NOT give both at the same time.",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("WOUND CARE:", s["heading"]))
    story.append(Paragraph(
        "Keep the 3 small bandages dry for 48 hours. Steri-strips will "
        "fall off on their own in 7-10 days. Watch for increasing redness, "
        "swelling, or yellow drainage.",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("ACTIVITY:", s["heading"]))
    story.append(Paragraph(
        "No PE, sports, or rough play for 2 weeks. Light walking is fine "
        "from day 1. Return to school when your child feels ready, usually "
        "3-5 days.",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("DIET:", s["heading"]))
    story.append(Paragraph(
        "Start with clear liquids, advance to regular diet as tolerated.",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("WHEN TO CALL OR GO TO THE ER:", s["heading"]))
    story.append(Paragraph(
        "Fever above 38.5C (101.3F) / Vomiting that won't stop / Severe "
        "belly pain / Wound looks infected",
        s["body"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("FOLLOW-UP:", s["heading"]))
    story.append(Paragraph(
        "Dr. Sarah Nguyen, Pediatric Surgery — April 17, 2026 at 2:00 PM — "
        "call 773-555-0291 to confirm.",
        s["body"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "Discharge condition: Stable, tolerating oral fluids, pain "
        "controlled on oral medications.",
        s["body_small"],
    ))

    doc.build(story)
    return out


# ── Fixture 14: Multi-page distractor (DM + sepsis, 6 pages) ────────────────

def build_fixture_14() -> Path:
    """6-page document: admission meds + IV inpatient meds act as
    distractors; the real discharge medication list is on page 5."""
    out = OUT_DIR / "fixture_14_multipage_sepsis.pdf"
    s = _styles()
    doc = SimpleDocTemplate(
        str(out), pagesize=LETTER,
        leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
    )
    story = []

    # ── PAGE 1: admission note ─────────────────────────────────────────────
    story.append(Paragraph("ADMISSION NOTE", s["title"]))
    story.append(Paragraph(
        "Patient: Harold Greene   DOB: 1954-11-02   MRN: 77188423<br/>"
        "Admission Date: 2026-04-03   Attending: Dr. Priya Desai",
        s["body"],
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "CHIEF COMPLAINT: Fever, confusion, and foot wound drainage x 2 days.",
        s["body"],
    ))
    story.append(Paragraph(
        "HPI: 71-year-old man with PMH type 2 diabetes mellitus, chronic "
        "kidney disease stage 3b, hypertension, and diabetic foot ulcer "
        "presented with fever to 39.1C, altered mental status, and "
        "purulent drainage from the right plantar ulcer. Lactate 4.1, "
        "WBC 18.9. Meets sepsis criteria.",
        s["body"],
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "HOME / ADMISSION MEDICATIONS (on arrival):<br/>"
        "1. Metformin 1000mg PO BID<br/>"
        "2. Glipizide 5mg PO QD<br/>"
        "3. Lisinopril 10mg PO QD<br/>"
        "4. Atorvastatin 20mg PO QD",
        s["body"],
    ))
    story.append(PageBreak())

    # ── PAGE 2: hospital course ────────────────────────────────────────────
    story.append(Paragraph("HOSPITAL COURSE (Day 1-3)", s["heading"]))
    story.append(Paragraph(
        "Patient was admitted to the MICU for sepsis from a diabetic foot "
        "ulcer. Blood cultures x 2 and wound cultures were drawn. "
        "Broad-spectrum antibiotics were initiated empirically after "
        "cultures. Fluid resuscitation with 4L LR. Lactate cleared by "
        "hospital day 2. Mental status improved with treatment of "
        "infection and correction of hyperglycemia (admission glucose 412).",
        s["body"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("HOSPITAL COURSE (Day 4-6)", s["heading"]))
    story.append(Paragraph(
        "Bedside debridement of plantar ulcer at bedside by podiatry on "
        "day 4. Wound cultures grew MSSA, narrowed antibiotics. Glycemic "
        "control transitioned from insulin drip to basal-bolus regimen "
        "then back to oral agents as renal function recovered. Creatinine "
        "peaked at 2.8 on day 2, improving to 1.6 at discharge.",
        s["body"],
    ))
    story.append(PageBreak())

    # ── PAGE 3: MAR (distractor — IV inpatient meds) ───────────────────────
    story.append(Paragraph("MEDICATION ADMINISTRATION RECORD", s["heading"]))
    story.append(Paragraph(
        "Inpatient medications administered during this admission "
        "(hospital stay only — NOT discharge medications):",
        s["body_small"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "1. Vancomycin 1.25g IV Q12H — days 1 through 4<br/>"
        "2. Piperacillin-Tazobactam 3.375g IV Q6H — days 1 through 4<br/>"
        "3. Cefazolin 2g IV Q8H — days 5 through 6 (narrowed after cultures)<br/>"
        "4. Insulin drip — continuous infusion days 1 through 3<br/>"
        "5. Regular insulin sliding scale — subcutaneous days 4 through 6<br/>"
        "6. Normal saline 125 mL/hr IV — days 1 through 3<br/>"
        "7. Acetaminophen 650mg PO PRN fever — as needed<br/>"
        "8. Ondansetron 4mg IV PRN nausea — as needed",
        s["body"],
    ))
    story.append(PageBreak())

    # ── PAGE 4: consults / labs ────────────────────────────────────────────
    story.append(Paragraph("CONSULTS", s["heading"]))
    story.append(Paragraph(
        "Podiatry (Dr. Keller) — performed bedside debridement day 4. "
        "Recommends offloading with diabetic shoe and wound check in 1 "
        "week.<br/>"
        "Infectious Disease (Dr. Wolfe) — recommended IV to oral "
        "transition after source control and clinical improvement.<br/>"
        "Endocrinology (Dr. Ahn) — recommended holding Glipizide due to "
        "risk of hypoglycemia with renal insufficiency; start SGLT2 "
        "inhibitor once eGFR stable > 30.",
        s["body"],
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph("KEY LAB TRENDS", s["heading"]))
    story.append(Paragraph(
        "Creatinine: 1.4 (baseline) → 2.8 (peak) → 1.6 (discharge)<br/>"
        "eGFR: 42 → 22 → 38<br/>"
        "Glucose: 412 (admit) → 140-180 (discharge range)<br/>"
        "HbA1c: 9.2% (admit)<br/>"
        "WBC: 18.9 → 7.1",
        s["body"],
    ))
    story.append(PageBreak())

    # ── PAGE 5: the real discharge medications ─────────────────────────────
    story.append(Paragraph("DISCHARGE SUMMARY", s["title"]))
    story.append(Paragraph(
        "Discharge Date: 2026-04-09   Disposition: Home with home health "
        "wound care",
        s["body"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("DISCHARGE DIAGNOSES", s["heading"]))
    story.append(Paragraph(
        "Principal: Sepsis due to diabetic foot infection, resolved<br/>"
        "Secondary: Type 2 diabetes mellitus (A1c 9.2%); Acute kidney "
        "injury on chronic kidney disease stage 3b, improving; "
        "Hypertension; Diabetic foot ulcer, right plantar, s/p "
        "debridement",
        s["body"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "DISCHARGE MEDICATIONS (what to take at home):", s["heading"]))
    story.append(Paragraph(
        "1. Metformin 500mg PO BID (dose REDUCED from 1000mg — "
        "kidney function improving but not baseline)<br/>"
        "2. Lisinopril 5mg PO QD (dose REDUCED from 10mg)<br/>"
        "3. Dapagliflozin 10mg PO QD (NEW — added for diabetes)<br/>"
        "4. Aspirin 81mg PO QD (NEW — cardiovascular protection)<br/>"
        "5. Atorvastatin 20mg PO QD (continued — no change)<br/>"
        "STOP: Glipizide (risk of low blood sugar with new regimen)",
        s["body"],
    ))
    story.append(PageBreak())

    # ── PAGE 6: follow-up + activity ───────────────────────────────────────
    story.append(Paragraph("FOLLOW-UP APPOINTMENTS", s["heading"]))
    story.append(Paragraph(
        "• Primary Care — Dr. Jessica Lin — 2026-04-16 — diabetes and "
        "blood pressure check — (312) 555-0312<br/>"
        "• Podiatry — Dr. Keller — 2026-04-15 — wound check and dressing "
        "change — (312) 555-0440<br/>"
        "• Nephrology — Dr. Huang — 2026-04-30 — follow-up on kidney "
        "function — (312) 555-0199<br/>"
        "• Endocrinology — Dr. Ahn — 2026-05-08 — review diabetes "
        "regimen — (312) 555-0288",
        s["body"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("ACTIVITY AND DIET", s["heading"]))
    story.append(Paragraph(
        "Offload the right foot with diabetic shoe. No walking barefoot. "
        "Diabetic diet, low sodium (< 2 g/day). Home health nurse will "
        "visit 3x per week for wound care.",
        s["body"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("WHEN TO CALL OR GO TO THE ER", s["heading"]))
    story.append(Paragraph(
        "• Fever above 101°F (38.3°C)<br/>"
        "• New or worsening redness, warmth, or drainage from the foot "
        "wound<br/>"
        "• Confusion or unusual sleepiness<br/>"
        "• Blood sugar below 70 or above 400<br/>"
        "• Chest pain or shortness of breath<br/>"
        "• Significant decrease in urination",
        s["body"],
    ))

    doc.build(story)
    return out


# ── Driver ──────────────────────────────────────────────────────────────────

BUILDERS = [
    ("Fixture 9  — Epic CHF",              build_fixture_09),
    ("Fixture 10 — Cerner pneumonia",      build_fixture_10),
    ("Fixture 11 — Word knee replacement", build_fixture_11),
    ("Fixture 12 — Two-column post-MI",    build_fixture_12),
    ("Fixture 13 — Pediatric appendectomy", build_fixture_13),
    ("Fixture 14 — Multi-page sepsis",     build_fixture_14),
]


if __name__ == "__main__":
    for label, builder in BUILDERS:
        path = builder()
        size_kb = path.stat().st_size / 1024
        print(f"  {label:42s}  ->  {path.name}  ({size_kb:.1f} KB)")
    print(f"\nAll fixtures written to: {OUT_DIR}")
