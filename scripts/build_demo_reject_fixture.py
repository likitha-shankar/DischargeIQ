#!/usr/bin/env python3
"""
Build the non-discharge PDF used by demo step 4 (graceful degradation).

The demo script's stable dataset calls for "a plumbing-invoice / non-discharge
PDF" to show the router's `rejected` path: a document that is clearly not a
discharge summary should produce one honest "try another document" screen
rather than seven empty tabs. No such file existed in the repo, so the step
depended on whatever the presenter could find on the day.

This writes a wholly invented plumbing invoice - no real business, no real
person, no real address - to test-data/not_a_discharge_invoice.pdf.

Owner: Likitha Shankar.

Usage:
    python scripts/build_demo_reject_fixture.py

Dependencies:
    reportlab (already required for the synthetic corpus tooling).
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# Deliberately mundane and unmistakably non-clinical. The router should reject
# on the document's own terms, not because the text is gibberish - a garbled
# page would test the parser, not the classifier.
_BUSINESS = "Northside Plumbing & Drain Co."
_LINES = [
    ("Invoice number", "INV-2026-4471"),
    ("Invoice date", "August 3, 2026"),
    ("Due date", "September 2, 2026"),
    ("Customer", "Unit 4B, Maple Court Apartments"),
]
_WORK = [
    ("Service call - kitchen sink backup", "$95.00"),
    ("Snake main drain line, 40 ft", "$180.00"),
    ("Replace P-trap assembly", "$62.50"),
    ("Parts: PVC fittings and sealant", "$28.75"),
    ("Labor, 2.5 hours at $85/hr", "$212.50"),
]
_FOOTER = [
    "Payment due within 30 days. Late payments accrue 1.5% monthly interest.",
    "Warranty: 90 days on labor, manufacturer terms on parts.",
    "Questions about this invoice? Reply to the email it arrived with.",
]


def build(destination: Path) -> Path:
    """
    Write the invoice PDF.

    Args:
        destination: Path of the PDF to create. Parent directories must exist.

    Returns:
        The path written, for logging by the caller.

    Raises:
        OSError: If the file cannot be written.
    """
    pdf = canvas.Canvas(str(destination), pagesize=LETTER)
    width, height = LETTER
    y = height - inch

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(inch, y, _BUSINESS)
    y -= 0.28 * inch
    pdf.setFont("Helvetica", 10)
    pdf.drawString(inch, y, "Licensed & insured - serving the metro area since 1998")
    y -= 0.45 * inch

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(inch, y, "INVOICE")
    y -= 0.3 * inch

    pdf.setFont("Helvetica", 11)
    for label, value in _LINES:
        pdf.drawString(inch, y, f"{label}: {value}")
        y -= 0.22 * inch

    y -= 0.2 * inch
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(inch, y, "Work performed")
    y -= 0.26 * inch

    pdf.setFont("Helvetica", 11)
    total = 0.0
    for description, amount in _WORK:
        pdf.drawString(inch, y, description)
        pdf.drawRightString(width - inch, y, amount)
        total += float(amount.lstrip("$"))
        y -= 0.24 * inch

    y -= 0.12 * inch
    pdf.line(inch, y, width - inch, y)
    y -= 0.26 * inch
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(inch, y, "Total due")
    pdf.drawRightString(width - inch, y, f"${total:,.2f}")

    y -= 0.5 * inch
    pdf.setFont("Helvetica", 9)
    for line in _FOOTER:
        pdf.drawString(inch, y, line)
        y -= 0.2 * inch

    pdf.showPage()
    pdf.save()
    return destination


def main() -> None:
    """Write the fixture next to the other committed demo documents."""
    target = Path(__file__).resolve().parents[1] / "test-data" / "not_a_discharge_invoice.pdf"
    build(target)
    print(f"Wrote {target} ({target.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
