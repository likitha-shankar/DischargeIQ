"""
Builds the one-page clinician field card.

This is the sheet carried into the room while running the demo, not the prep
document. Two columns on letter portrait so the whole thing fits on one side
of one page - a second page would be turned over and lost mid-conversation.

Content is the demo-time subset of docs/CLINICIAN_INTERVIEW_GUIDE.md: the
screen-by-screen questions and the gamification block, plus the three
questions that must be asked at fixed moments (before the demo, at the end)
and space to write.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

TEAL = HexColor("#0F6E56")
TEAL_MID = HexColor("#1D9E75")
INK = HexColor("#0A2A1F")
GREY = HexColor("#5A6B66")
RED = HexColor("#C0392B")
RULE = HexColor("#D8E9E3")

OUT = ("/Users/likitha/Desktop/hmm/masters/sem4/healthcare & AI/DischargeIQ/"
       "docs/CLINICIAN_FIELD_CARD.pdf")

PW, PH = LETTER
MARGIN = 0.45 * inch
GUTTER = 0.28 * inch
COL_W = (PW - 2 * MARGIN - GUTTER) / 2
COL_X = [MARGIN, MARGIN + COL_W + GUTTER]

c = canvas.Canvas(OUT, pagesize=LETTER)
c.setTitle("DischargeIQ - clinician field card")


class Cursor:
    """Tracks the write position and flows into the second column when full."""

    def __init__(self):
        self.col = 0
        self.y = PH - MARGIN

    @property
    def x(self):
        return COL_X[self.col]

    def need(self, height):
        """Move to the next column if `height` will not fit below the cursor."""
        if self.y - height < MARGIN:
            self.col += 1
            self.y = PH - MARGIN
            if self.col > 1:
                raise RuntimeError("content overflows one page - trim the card")


cur = Cursor()


def newcol():
    """Start the second column deliberately, rather than on overflow."""
    cur.col += 1
    cur.y = PH - MARGIN


def wrap(text, font, size, width):
    """Greedy wrap into lines that fit `width`."""
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if c.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def heading(text, color=TEAL, size=9.5, gap_before=7):
    cur.need(size + gap_before + 3)
    cur.y -= gap_before
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", size)
    c.drawString(cur.x, cur.y, text.upper())
    cur.y -= 3
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(cur.x, cur.y, cur.x + COL_W, cur.y)
    cur.y -= 11


def q(number, text, color=INK, bold=False, size=8.2, indent=13):
    """One numbered question, wrapped and hanging-indented."""
    font = "Helvetica-Bold" if bold else "Helvetica"
    lines = wrap(text, font, size, COL_W - indent)
    cur.need(len(lines) * (size + 1.9) + 3)
    c.setFillColor(TEAL_MID)
    c.setFont("Helvetica-Bold", size)
    c.drawString(cur.x, cur.y, f"{number}")
    c.setFillColor(color)
    c.setFont(font, size)
    for i, ln in enumerate(lines):
        c.drawString(cur.x + indent, cur.y, ln)
        cur.y -= size + 1.9
    cur.y -= 3


def note(text, color=GREY, size=7.4, italic=True):
    font = "Helvetica-Oblique" if italic else "Helvetica"
    lines = wrap(text, font, size, COL_W - 13)
    cur.need(len(lines) * (size + 1.6) + 3)
    c.setFillColor(color)
    c.setFont(font, size)
    for ln in lines:
        c.drawString(cur.x + 13, cur.y, ln)
        cur.y -= size + 1.6
    cur.y -= 3


def writing_lines(count, gap=13):
    """Ruled lines for notes taken in the room."""
    cur.need(count * gap + 4)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    for _ in range(count):
        cur.y -= gap
        c.line(cur.x, cur.y, cur.x + COL_W, cur.y)
    cur.y -= 6


# ── Title ────────────────────────────────────────────────────────────────────
c.setFillColor(INK)
c.setFont("Helvetica-Bold", 14)
c.drawString(cur.x, cur.y - 11, "DischargeIQ - clinician session")
cur.y -= 26
c.setFillColor(GREY)
c.setFont("Helvetica", 8)
c.drawString(cur.x, cur.y, "Show first, ask second. Do not defend. Ask for the failure twice.")
cur.y -= 12

# ── Ask before the demo ──────────────────────────────────────────────────────
heading("Ask BEFORE showing anything", color=RED, gap_before=2)
q("1", "What do you say out loud to patients that never makes it onto the paper?",
  bold=True)
note("Highest-value question here. A spoken-only instruction is invisible to us.")
q("2", "What would make you refuse to let a patient use something like this?",
  bold=True)
note("Ask before the demo so the answer is not shaped by what they just saw.")

# ── Summary screen ───────────────────────────────────────────────────────────
heading("Summary screen")
q("3", "Read this as the patient. Is anything wrong?")
q("4", "Anything right but misleading?")
q("5", "Simplified past the point of being useful?")
q("6", "Anything in the original that should be here and is not?")

# ── Medications ──────────────────────────────────────────────────────────────
heading("Medications")
q("7", "Names, doses, frequencies - exactly as the source?")
q("8", "The 'why you take it' explanation - safe, or overstepping?")
q("9", "Anything a patient must be told that is missing?")

# ── Warning signs ────────────────────────────────────────────────────────────
heading("Warning signs (safety-critical)", color=RED)
q("10", "Any symptom in the wrong tier?")
q("11", "Anything in 'call your doctor' that should be higher?", bold=True)
note("Wrong direction is the dangerous one. Ask this specifically.")
q("12", "Anything missing you would always tell this patient?")
q("13", "Only 34% of real documents list any warning signs. When there are none "
        "we show generic 911 advice, labelled as not from their document. "
        "Safer than nothing, or does it cross a line?")

# ── Chatbot ──────────────────────────────────────────────────────────────────
COL1_TAIL_Y = cur.y
newcol()
heading("Chatbot - hand them the phone", gap_before=0)
q("14", "Ask something the document answers. Right?")
q("15", "Ask something it does not answer. Refusal helpful, or broken?")
q("16", "Ask 'should I stop taking this?' - does the decline feel safe?")
q("17", "A question this should never attempt, even with a disclaimer?")

# ── Quiz ─────────────────────────────────────────────────────────────────────
heading("Quiz")
q("18", "Baseline gives no feedback so it measures rather than teaches. Sensible?")
q("19", "Right five domains? Diagnosis, meds, follow-up, activity, red flags.")
q("20", "Would a patient just out of hospital tolerate being quizzed?")

# ── Gamification ─────────────────────────────────────────────────────────────
heading("Gamification - ask as its own topic", color=TEAL)
note("No timers, no streaks to lose, no leaderboards, nothing turns red.",
     italic=False)
q("21", "Does a rewards layer belong in a product used the week someone got "
        "out of hospital?", bold=True)
q("22", "Where is the line between encouraging and pressuring a patient?")
q("23", "Daily mood check-in, with a care-team nudge after several rough days. "
        "Useful signal or overreach?")
q("24", "Would you want to see engagement data - or does that turn a "
        "comprehension tool into a compliance tool?")
q("25", "A patient group you would NOT show this to?")

# ── Judgement ────────────────────────────────────────────────────────────────
heading("Before they leave", color=RED)
q("26", "Would you hand this to your own patient? If not, what one thing "
        "would change that?", bold=True)
q("27", "Where is this most likely to hurt someone - not annoy, hurt?", bold=True)
q("28", "Would you review 5-10 documents, self-paced, 1-2 hours total? "
        "If not you, who?")

# ── Notes ────────────────────────────────────────────────────────────────────
heading("Verbatim - their words, not yours")
note("Every 'I would never...'. Anything they corrected. Anything they "
     "hesitated over - hesitation is a finding.", italic=False)
writing_lines(6)

c.setFillColor(RED)
c.setFont("Helvetica-Bold", 8)
cur.need(24)
c.drawString(cur.x, cur.y, "The one thing you did not want to hear:")
cur.y -= 4
writing_lines(3)


def rule_out_rest_of_column():
    """Fill the remainder of the current column with note ruling.

    A field card with blank space at the foot reads as unfinished, and ruled
    space actually gets written on during the session.
    """
    remaining = int((cur.y - MARGIN) // 13)
    if remaining > 0:
        writing_lines(remaining)


rule_out_rest_of_column()

# Column one stopped after the warning-signs block, so rule its tail as well.
cur.col = 0
cur.y = COL1_TAIL_Y
c.setFillColor(TEAL)
c.setFont("Helvetica-Bold", 8)
cur.y -= 10
c.drawString(cur.x, cur.y, "Notes")
cur.y -= 5
rule_out_rest_of_column()

c.save()
print(f"saved: {OUT}")
