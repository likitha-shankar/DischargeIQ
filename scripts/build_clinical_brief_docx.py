"""
Builds the DischargeIQ clinical review brief as an editable Word document.

Produces docs/DischargeIQ_Clinical_Brief_Liebovitz.docx - a nine-section
overview written for Dr. David M. Liebovitz covering why the product exists,
what it does, how the pipeline works, where safety is enforced, what it refuses
to do, the evidence base, build status, the decisions needing clinical input,
and the limits of the prototype.

This module owns layout only. All prose lives in clinical_brief_content.py so
the brief can be reworded without touching rendering. Depends on python-docx.

Run: python3 scripts/build_clinical_brief_docx.py
"""

import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor, Inches

# Allow the sibling content module to import when run from the repo root,
# where scripts/ is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clinical_brief_content import (  # noqa: E402
    ABSTRACT,
    CLOSING,
    HOW_IT_WORKS,
    LIMITATIONS,
    PROBLEM_BULLETS,
    PROBLEM_INTRO,
    QUESTIONS,
    QUESTIONS_INTRO,
    SAFETY_BOUNDARIES,
    SOURCES,
    STATUS_ROWS,
    TECHNICAL_INTRO,
    TECHNICAL_ROWS,
    VALIDATION_BULLETS,
    VALIDATION_INTRO,
    WHAT_IT_DOES_INTRO,
    WHAT_IT_DOES_ROWS,
)

# Visual identity. Deep navy headings, teal subtitle - readable in print and
# unobtrusive when the reader edits the file in Word.
NAVY = RGBColor(0x1F, 0x3B, 0x63)
TEAL = RGBColor(0x1F, 0x6F, 0x6B)
GREY = RGBColor(0x55, 0x55, 0x55)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "DischargeIQ_Clinical_Brief_Liebovitz.docx"
SCREENSHOT_DIR = REPO_ROOT / "docs" / "deck-assets" / "brief"

# Phone screenshots are 1080x2400. At 1.9in wide two sit side by side inside
# Word's default margins without overflowing the page.
SCREENSHOT_WIDTH = Inches(1.9)


def style_document(document):
    """
    Sets the base body font for the whole document.

    Word inherits every paragraph style from 'Normal', so setting it once here
    keeps the document editable without per-run formatting fighting the user.

    Args:
        document: The docx Document being built.
    """
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)


def add_title_block(document):
    """Adds the product name, subtitle, addressee line, and abstract box."""
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("DISCHARGEIQ")
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = NAVY

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Product, Safety, and Validation Overview")
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = TEAL

    addressee = document.add_paragraph()
    addressee.alignment = WD_ALIGN_PARAGRAPH.CENTER
    addressee.paragraph_format.space_after = Pt(0)
    run = addressee.add_run("Prepared for Dr. David M. Liebovitz")
    run.font.size = Pt(11)
    run.font.italic = True
    run.font.color.rgb = GREY

    sender = document.add_paragraph()
    sender.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sender.add_run("Likitha Shankar, product lead - DischargeIQ")
    run.font.size = Pt(9.5)
    run.font.color.rgb = GREY

    # The abstract sits in a single-cell table so it renders as a shaded box,
    # which is how the reader's eye finds the scope statement first.
    box = document.add_table(rows=1, cols=1)
    box.style = "Table Grid"
    cell = box.cell(0, 0)
    cell.text = ABSTRACT
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(0)
        for run in paragraph.runs:
            run.font.size = Pt(10.5)
    document.add_paragraph()


def add_heading(document, text):
    """Adds a numbered section heading in the document's navy style."""
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(14)
    run = paragraph.add_run(text)
    run.font.size = Pt(13)
    run.font.bold = True
    run.font.color.rgb = NAVY


def add_bullets(document, items):
    """Adds a list of body bullets."""
    for item in items:
        document.add_paragraph(item, style="List Bullet")


def add_numbered(document, items):
    """Adds a list of numbered steps."""
    for item in items:
        document.add_paragraph(item, style="List Number")


def add_definition_table(document, rows):
    """
    Adds a two-column term/description table.

    Args:
        rows: Sequence of (term, description) pairs. The term column is bolded
              and fixed narrow so descriptions get the remaining width.
    """
    table = document.add_table(rows=0, cols=2)
    table.style = "Light List Accent 1"
    for term, description in rows:
        cells = table.add_row().cells
        cells[0].width = Inches(1.6)
        cells[1].width = Inches(4.6)
        run = cells[0].paragraphs[0].add_run(term)
        run.font.bold = True
        cells[1].text = description
    document.add_paragraph()


def add_figure(document, images, caption):
    """
    Places screenshots side by side with a shared caption.

    Uses a borderless table so Word keeps the images on one line and the user
    can still move them while editing. Missing files are skipped rather than
    raising, so the brief still builds on a machine without the assets.

    Args:
        images: Sequence of Paths to image files.
        caption: Figure caption rendered below the row.
    """
    present = [path for path in images if path.exists()]
    if not present:
        return

    table = document.add_table(rows=1, cols=len(present))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, path in zip(table.rows[0].cells, present):
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.add_run().add_picture(str(path), width=SCREENSHOT_WIDTH)

    label = document.add_paragraph()
    label.alignment = WD_ALIGN_PARAGRAPH.CENTER
    label.paragraph_format.space_after = Pt(12)
    run = label.add_run(caption)
    run.font.size = Pt(9)
    run.font.italic = True
    run.font.color.rgb = GREY


def add_questions(document, questions):
    """
    Adds the clinical-review questions in product-manager framing.

    Each question carries labelled lead-in lines - the decision owned, what is
    already shipped, and what changes on either answer - so it is visible that
    the question is being asked in order to act on the answer.

    Args:
        questions: Sequence of (question_text, [(label, text), ...]) pairs.
    """
    for index, (question, notes) in enumerate(questions, start=1):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Inches(0.25)
        paragraph.paragraph_format.space_after = Pt(3)
        number = paragraph.add_run(f"{index}. ")
        number.font.bold = True
        run = paragraph.add_run(question)
        run.font.bold = True

        for label, text in notes:
            note = document.add_paragraph()
            note.paragraph_format.left_indent = Inches(0.5)
            note.paragraph_format.space_after = Pt(2)
            label_run = note.add_run(f"{label} ")
            label_run.font.size = Pt(9.5)
            label_run.font.bold = True
            label_run.font.color.rgb = TEAL
            body_run = note.add_run(text)
            body_run.font.size = Pt(9.5)
            body_run.font.color.rgb = GREY

        document.add_paragraph().paragraph_format.space_after = Pt(6)


def add_sources(document, sources):
    """Adds the supporting-sources block: title, why it was used, and URL."""
    label = document.add_paragraph()
    run = label.add_run("WHAT INFORMED THE DESIGN")
    run.font.size = Pt(9.5)
    run.font.bold = True
    run.font.color.rgb = TEAL

    for name, purpose, url in sources:
        heading = document.add_paragraph()
        heading.paragraph_format.space_after = Pt(0)
        run = heading.add_run(name)
        run.font.bold = True
        run.font.color.rgb = NAVY

        body = document.add_paragraph()
        body.paragraph_format.left_indent = Inches(0.25)
        body.paragraph_format.space_after = Pt(0)
        body.add_run(purpose)

        link = document.add_paragraph()
        link.paragraph_format.left_indent = Inches(0.25)
        run = link.add_run(url)
        run.font.size = Pt(9)
        run.font.color.rgb = TEAL


def build_document():
    """
    Assembles and writes the brief.

    Returns:
        Path: The location of the written .docx file.
    """
    document = Document()
    style_document(document)

    add_title_block(document)

    add_heading(document, "1. Why DischargeIQ Exists")
    document.add_paragraph(PROBLEM_INTRO)
    add_bullets(document, PROBLEM_BULLETS)

    add_heading(document, "2. What the App Does Today")
    document.add_paragraph(WHAT_IT_DOES_INTRO)
    add_definition_table(document, WHAT_IT_DOES_ROWS)
    add_figure(
        document,
        [SCREENSHOT_DIR / "tab1_what.png", SCREENSHOT_DIR / "tab2_meds.png"],
        "Figure 1. What happened, and Your medications. Every extracted item carries a \"see where "
        "this comes from\" link that opens the exact source line. Medications are labelled new, "
        "changed, continued, or discontinued, and \"why you're taking this\" explains the reason "
        "without ever advising a dose change.",
    )
    add_figure(
        document,
        [SCREENSHOT_DIR / "tab3_appts.png", SCREENSHOT_DIR / "tab5_recovery.png"],
        "Figure 2. Your appointments, sorted soonest first with the stated reason for each and a "
        "one-tap calendar entry, and Your recovery, which separates activity limits from dietary "
        "limits and carries the condition recorded at discharge.",
    )

    add_heading(document, "3. The Pipeline, End to End")
    add_numbered(document, HOW_IT_WORKS)
    add_figure(
        document,
        [SCREENSHOT_DIR / "tab6_quiz.png", SCREENSHOT_DIR / "chat.png"],
        "Figure 3. Test yourself, the teach-back quiz, taken once before reading with no hints or "
        "score shown and again afterwards - the delta is the comprehension figure we report. "
        "Beside it, the grounded chat, which states on its own header that answers come only from "
        "the patient's document.",
    )

    add_heading(document, "4. Where Safety Lives in the Architecture")
    document.add_paragraph(TECHNICAL_INTRO)
    add_definition_table(document, TECHNICAL_ROWS)
    add_figure(
        document,
        [SCREENSHOT_DIR / "tab4_warning.png", SCREENSHOT_DIR / "tab7_check.png"],
        "Figure 4. The two screens most in need of your review. Warning signs (left) applies the "
        "three-tier structure and opens with a standing caveat that the guide is AI-generated. "
        "Discharge check (right) is the gap report: a score, a plain summary, and each gap written "
        "as the question a patient would actually ask - addressed to the care team, labelled as "
        "not a diagnosis.",
    )

    add_heading(document, "5. What the System Will Not Do")
    add_bullets(document, SAFETY_BOUNDARIES)

    add_heading(document, "6. Evidence Base and How We Are Validating")
    document.add_paragraph(VALIDATION_INTRO)
    add_bullets(document, VALIDATION_BULLETS)
    add_sources(document, SOURCES)

    add_heading(document, "7. Where the Build Stands, August 2026")
    add_definition_table(document, STATUS_ROWS)

    add_heading(document, "8. Five Decisions I Need Clinical Input On")
    document.add_paragraph(QUESTIONS_INTRO)
    add_figure(
        document,
        [SCREENSHOT_DIR / "goals.png"],
        "Figure 5. The screen behind questions 1 and 3: the patient chooses what they most want to "
        "understand, which reorders their reading. Nothing is hidden, and warning signs stay in "
        "the quiz whatever they pick.",
    )
    add_questions(document, QUESTIONS)
    document.add_paragraph(CLOSING)

    add_heading(document, "9. What This Is Not")
    document.add_paragraph(LIMITATIONS)

    footer = document.sections[0].footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("DischargeIQ  |  Clinical Review Brief")
    run.font.size = Pt(8.5)
    run.font.color.rgb = GREY

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT_PATH)
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Wrote {build_document()}")
