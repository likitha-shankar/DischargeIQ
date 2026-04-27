"""
Generate realistic hospital-style PDF fixtures for extraction testing.

Run from repo root:
  python dischargeiq/tests/fixtures/build_real_world_fixtures.py

Requires: reportlab
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.pdfgen import canvas

OUT_DIR = Path(__file__).resolve().parent


def _styles():
    s = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=s["Normal"],
        fontSize=10,
        leading=13,
        spaceAfter=6,
    )
    hdr = ParagraphStyle(
        "Hdr",
        parent=s["Heading2"],
        fontSize=12,
        leading=14,
        spaceAfter=8,
    )
    small = ParagraphStyle(
        "Small",
        parent=s["Normal"],
        fontSize=9,
        leading=11,
    )
    return body, hdr, small


def build_real_01_er_simple() -> None:
    """ER discharge — checkboxes, minimal structure, no med list."""
    path = OUT_DIR / "real_01_er_simple.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    y = h - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "EMERGENCY DEPARTMENT DISCHARGE INSTRUCTIONS")
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Patient: James Wilson    DOB: 1958-03-14")
    y -= 16
    c.drawString(50, y, "Date: 2026-04-15    Discharging provider: Dr. Chen, MD")
    y -= 28
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Clinical impression")
    y -= 16
    c.setFont("Helvetica", 10)
    for line in [
        "Chest pain, etiology unclear",
    ]:
        c.drawString(50, y, line)
        y -= 14
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Please check all that apply (instructions given):")
    y -= 20
    c.setFont("Helvetica", 10)
    checks = [
        "☑ Follow up with your primary care doctor in 3-5 days",
        "☑ Return to ER if chest pain returns or worsens",
        "☑ Return to ER if shortness of breath develops",
        "☑ Continue your home medications",
    ]
    for line in checks:
        c.drawString(55, y, line)
        y -= 16
    y -= 12
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Instructions")
    y -= 16
    c.setFont("Helvetica", 10)
    prose = (
        "You were evaluated for chest pain. Your EKG and initial labs were normal. "
        "This does not rule out cardiac cause. Follow up is very important. "
        "If you have questions about these instructions, contact your primary care office."
    )
    for i in range(0, len(prose), 95):
        c.drawString(50, y, prose[i : i + 95])
        y -= 14
    c.save()


def build_real_02_er_with_new_rx() -> None:
    path = OUT_DIR / "real_02_er_with_new_rx.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    y = letter[1] - 50
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, "ED After-Visit Summary")
    y -= 24
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Patient: Maria Gonzalez    DOB: 1972-08-22")
    y -= 14
    c.drawString(50, y, "Visit date: 2026-04-18")
    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Diagnosis")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Urinary tract infection")
    y -= 22
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "New prescription")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Nitrofurantoin 100mg twice daily for 5 days")
    y -= 22
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Return precautions")
    y -= 16
    for line in [
        "- Fever above 101°F",
        "- Symptoms not improving after 48 hours",
        "- Back or flank pain develops",
    ]:
        c.drawString(55, y, line)
        y -= 14
    y -= 10
    c.drawString(50, y, "Follow-up: Follow up with your doctor if symptoms persist.")
    c.save()


def build_real_03_narrative_style() -> None:
    path = OUT_DIR / "real_03_narrative_style.pdf"
    body, hdr, _ = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=letter, topMargin=50, bottomMargin=50)
    story = []
    story.append(Paragraph("University Medical Center — Discharge Summary", hdr))
    story.append(Paragraph("Patient: Robert Kim, 67-year-old male.", body))
    story.append(Paragraph("Admission date: 2026-04-08. Discharge date: 2026-04-11.", body))
    story.append(Spacer(1, 0.15 * inch))
    p1 = (
        "Mr. Kim was admitted through the emergency department with worsening dyspnea "
        "and increased sputum production on a background of known COPD. On arrival he "
        "was tachypneic with diffuse wheezes. Chest imaging showed hyperinflation without "
        "a new infiltrate. He was treated for acute exacerbation of COPD."
    )
    story.append(Paragraph(p1, body))
    p2 = (
        "During hospitalization he did not require mechanical ventilation. He received "
        "bronchodilator therapy and was started on oral corticosteroids and a short "
        "course of azithromycin. Symptoms improved steadily and he was ambulating on "
        "the ward without supplemental oxygen by day three."
    )
    story.append(Paragraph(p2, body))
    story.append(PageBreak())
    p3 = (
        "Discharge medications: Patient is discharged on Prednisone 40mg daily for 5 days, "
        "Azithromycin 250mg daily for 3 more days (this is day 2 of a 5-day course), "
        "Albuterol inhaler as needed for wheeze or shortness of breath, and his home "
        "Tiotropium 18mcg once daily."
    )
    story.append(Paragraph(p3, body))
    p4 = (
        "Follow-up and precautions: He should follow up with pulmonology in 2 weeks for "
        "post-hospital assessment. He should return to the emergency department "
        "immediately if he develops worsening shortness of breath, fever above 38.5°C, "
        "or inability to complete sentences in one breath."
    )
    story.append(Paragraph(p4, body))
    doc.build(story)


def build_real_04_icd_codes() -> None:
    path = OUT_DIR / "real_04_icd_codes.pdf"
    body, hdr, small = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=letter, topMargin=45, bottomMargin=45)
    story = []
    story.append(Paragraph("Inpatient Discharge Summary — Internal Medicine", hdr))
    story.append(Paragraph("Patient: Susan Park    DOB: 1965-11-02", body))
    story.append(Paragraph("Admission: 2026-04-10    Discharge: 2026-04-14", body))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("Diagnoses (problem list)", hdr))
    story.append(Paragraph("Primary: I50.9 — Heart failure, unspecified", body))
    story.append(Paragraph("Secondary: I10 — Essential hypertension", small))
    story.append(Paragraph("E11.9 — Type 2 diabetes mellitus without complications", small))
    story.append(Paragraph("N18.3 — Chronic kidney disease, stage 3", small))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("Discharge Medications", hdr))
    med_data = [
        ["Drug", "Dose", "Frequency", "Notes"],
        ["Furosemide", "40mg", "Once daily", "NEW — monitor weight daily"],
        ["Lisinopril", "10mg", "Once daily", "REDUCED from 20mg — kidney function"],
        ["Metoprolol", "25mg", "Twice daily", "CONTINUE"],
        ["Metformin", "500mg", "Twice daily", "CONTINUE — reduced dose CKD"],
        ["Insulin glargine", "10 units", "Bedtime", "CONTINUE"],
    ]
    t = Table(med_data, colWidths=[1.4 * inch, 0.9 * inch, 1.1 * inch, 2.4 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Outpatient Follow-Up", hdr))
    fu_data = [
        ["Specialty", "Provider", "Date", "Reason"],
        ["Cardiology", "Dr. Patel", "2026-04-21", "Weight and fluid status"],
        ["Nephrology", "Dr. Nguyen", "2026-04-28", "Creatinine recheck"],
    ]
    t2 = Table(fu_data, colWidths=[1.2 * inch, 1.2 * inch, 1.1 * inch, 2.3 * inch])
    t2.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(t2)
    story.append(PageBreak())
    story.append(Paragraph("RETURN PRECAUTIONS", hdr))
    story.append(
        Paragraph(
            "Seek emergency care for: sudden weight gain &gt;3 lbs in one day, "
            "worsening leg swelling, chest pain, or severe shortness of breath at rest.",
            body,
        )
    )
    doc.build(story)


def build_real_05_bilingual() -> None:
    path = OUT_DIR / "real_05_bilingual.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    y = h - 45
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "ER Discharge — Bilingual Instructions / Instrucciones bilingües")
    y -= 22
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "English")
    c.drawString(320, y, "Español")
    y -= 18
    c.setFont("Helvetica", 9)
    en = [
        "Diagnosis: Laceration repair, right hand",
        "Wound care: Keep clean and dry. Change dressing daily.",
        "Signs of infection: spreading redness, pus, fever, red streaks.",
        "Follow-up: clinic in 7-10 days for suture removal.",
        "Medication: Amoxicillin-clavulanate 875mg twice daily for 7 days.",
        "Return to ER: increasing redness, pus, fever, numbness in fingers.",
    ]
    es = [
        "Diagnóstico: Reparación de laceración, mano derecha",
        "Cuidado de la herida: Mantenga limpio y seco. Cambie el apósito diario.",
        "Signos de infección: enrojecimiento que se extiende, pus, fiebre, vetas rojas.",
        "Seguimiento: clínica en 7-10 días para retiro de puntos.",
        "Medicamento: Amoxicilina-ácido clavulánico 875mg dos veces al día por 7 días.",
        "Vuelva a urgencias: más enrojecimiento, pus, fiebre, entumecimiento en dedos.",
    ]
    for e_line, s_line in zip(en, es):
        c.drawString(50, y, e_line[:75])
        c.drawString(320, y, s_line[:75])
        y -= 13
    c.save()


def build_real_06_minimal_er() -> None:
    path = OUT_DIR / "real_06_minimal_er.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    y = letter[1] - 45
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, "DISCHARGE INSTRUCTIONS")
    y -= 22
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "[Patient label / barcode area — information not shown on copy]")
    y -= 28
    c.setFont("Helvetica", 10)
    for line in [
        "Diagnosis: BACK PAIN",
        "Treatment: Pain medications given in ER",
        "Medications to take at home: Ibuprofen 600mg every 6 hours as needed, "
        "Cyclobenzaprine 5mg three times daily as needed for muscle spasm",
        "Follow up with your doctor in 1 week",
        "Return to ER if: pain is unbearable, you have weakness or numbness in your "
        "legs, or you cannot urinate",
    ]:
        for i in range(0, len(line), 100):
            c.drawString(50, y, line[i : i + 100])
            y -= 13
        y -= 4
    c.save()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_real_01_er_simple()
    build_real_02_er_with_new_rx()
    build_real_03_narrative_style()
    build_real_04_icd_codes()
    build_real_05_bilingual()
    build_real_06_minimal_er()
    print("Wrote 6 PDFs to", OUT_DIR)


if __name__ == "__main__":
    main()
