"""
scripts/generate_scan_test_images.py

Generates SYNTHETIC "phone photo" test images of discharge paperwork for the
camera-scan path: clean printed pages through messy handwritten notes, with
realistic degradations (skew, shadow, blur, low light, noise). Content is
fully synthetic (Patient NN / MRN 000-TEST-NN, same convention as the locked
corpus) - no real patient data ever existed in these (hard rule 6).

Usage:
    python scripts/generate_scan_test_images.py
    open test-data/scan-photos/    # AirDrop to a phone, scan via "From photos"

Dependencies: Pillow; macOS system handwriting fonts (Bradley Hand,
Noteworthy, Chalkduster) with DejaVu/Helvetica fallbacks for printed text.
Deterministic per tier (fixed seeds) so retakes reproduce the same files.
"""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "test-data" / "scan-photos"

# Page and photo geometry: portrait paper on a darker table background,
# roughly what a phone camera produces at modest resolution.
PAPER_W, PAPER_H = 1240, 1650
PHOTO_W, PHOTO_H = 1500, 2000

_PRINT_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_HAND_FONTS = {
    "neat": "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "note": "/System/Library/Fonts/Supplemental/Noteworthy.ttc",
    "messy": "/System/Library/Fonts/Supplemental/Chalkduster.ttf",
}

PRINTED_TEXT = """MERCY GENERAL HOSPITAL - DISCHARGE SUMMARY

Patient: Patient 07          MRN: 000-TEST-07
Discharge date: July 8, 2026
Primary diagnosis: Heart failure with reduced ejection fraction

MEDICATIONS AT DISCHARGE
1. Furosemide 40 mg - take one tablet by mouth every morning (NEW)
2. Lisinopril 10 mg - take one tablet by mouth daily (NEW)
3. Metoprolol succinate 25 mg - take one tablet daily (CONTINUED)
4. Aspirin 81 mg - take one tablet daily (CONTINUED)

FOLLOW-UP APPOINTMENTS
- Cardiology: Dr. Chen, July 22, 2026 - medication review
- Primary care: Dr. Patel, July 15, 2026 - recheck weight and blood pressure

ACTIVITY
- Weigh yourself every morning after using the bathroom.
- Call your doctor if you gain more than 3 pounds in one day.
- No lifting over 10 pounds for 2 weeks.

DIET
- Limit salt to 2 grams per day. Avoid canned soups and deli meats.
- Limit fluids to 2 liters per day.

WARNING SIGNS - CALL 911
- Severe trouble breathing at rest
- Chest pain lasting more than a few minutes
- Fainting or new confusion

CALL YOUR DOCTOR
- Weight gain over 3 pounds in a day or 5 pounds in a week
- New or worse swelling in legs or belly
- Dizziness when standing

Discharge condition: Stable, ambulating independently."""

HANDWRITTEN_MEDS = """Discharge meds - Patient 12
MRN 000-TEST-12

Furosemide 40mg - 1 every AM
Lisinopril 10mg daily
Metoprolol 25mg daily
ASA 81mg daily

Weigh every morning!!
Call Dr if +3 lbs/day

Cardiology f/u July 22 - Dr Chen
PCP July 15 - Dr Patel

No salt, fluids max 2L
No lifting > 10 lbs x 2 wks

Call 911: bad breathing at rest,
chest pain, fainting"""

HANDWRITTEN_MESSY = """pt 12 MRN 000-TEST-12
HF - reduced EF

furosemide 40 qAM
lisinopril 10 qd
metop succ 25 qd
asa 81

wt daily - call if up 3lb
cards 7/22 chen
pcp 7/15 patel
2g Na, 2L fluid
call 911 - SOB at rest / CP / syncope"""

MIXED_FORM_FILLS = [
    ("Patient name:", "Patient 12"),
    ("Diagnosis:", "heart failure"),
    ("Water pill dose:", "40 mg every morning"),
    ("Next visit:", "July 22 - Dr. Chen"),
    ("Daily weight goal:", "call if +3 lbs"),
]


def _font(paths, size):
    """First loadable font from a path list (or single path) at a size."""
    if isinstance(paths, str):
        paths = [paths]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _paper(text, font, line_gap, margin=70, jitter=0, rng=None):
    """Render text onto a white paper image, optional per-line jitter/rotation."""
    img = Image.new("RGB", (PAPER_W, PAPER_H), (252, 251, 247))
    draw = ImageDraw.Draw(img)
    y = margin
    for line in text.split("\n"):
        x = margin + (rng.randint(-jitter, jitter) if jitter and rng else 0)
        if jitter and rng and line.strip():
            # Messy notes drift line by line - render each line rotated a hair.
            tile = Image.new("RGBA", (PAPER_W, line_gap * 2), (0, 0, 0, 0))
            ImageDraw.Draw(tile).text((x, 0), line, font=font, fill=(25, 25, 90))
            tile = tile.rotate(rng.uniform(-1.5, 1.5), resample=Image.BICUBIC)
            img.paste(tile, (0, y), tile)
        else:
            draw.text((x, y), line, font=font, fill=(30, 30, 35))
        y += line_gap
    return img


def _photograph(paper, angle=0.0, shadow=False, blur=0.0, dark=1.0, noise=0):
    """Turn a flat paper image into a 'phone photo': background, tilt, light."""
    photo = Image.new("RGB", (PHOTO_W, PHOTO_H), (98, 84, 72))  # wood table
    page = paper.rotate(angle, expand=True, resample=Image.BICUBIC,
                        fillcolor=(98, 84, 72))
    px = (PHOTO_W - page.width) // 2
    py = (PHOTO_H - page.height) // 2
    photo.paste(page, (px, py))
    if shadow:
        overlay = Image.new("L", photo.size, 0)
        ImageDraw.Draw(overlay).polygon(
            [(0, 0), (PHOTO_W, 0), (PHOTO_W, int(PHOTO_H * 0.45)), (0, int(PHOTO_H * 0.7))],
            fill=70,
        )
        overlay = overlay.filter(ImageFilter.GaussianBlur(120))
        photo = Image.composite(ImageEnhance.Brightness(photo).enhance(0.62), photo, overlay)
    if dark != 1.0:
        photo = ImageEnhance.Brightness(photo).enhance(dark)
    if blur:
        photo = photo.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        rng = random.Random(7)
        pixels = photo.load()
        for _ in range(noise):
            x, y = rng.randrange(PHOTO_W), rng.randrange(PHOTO_H)
            r, g, b = pixels[x, y]
            d = rng.randint(-28, 28)
            pixels[x, y] = (max(0, min(255, r + d)),) * 3 if r == g == b else (
                max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))
    return photo


def main() -> None:
    """Generate all difficulty tiers into test-data/scan-photos/."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    print_font = _font(_PRINT_FONTS, 26)
    printed = _paper(PRINTED_TEXT, print_font, 38)

    tiers = {
        # Printed page, four degradation levels.
        "01_printed_clean.jpg": _photograph(printed, angle=1.2),
        "02_printed_skewed_shadow.jpg": _photograph(printed, angle=6.5, shadow=True),
        "03_printed_blurred.jpg": _photograph(printed, angle=2.0, blur=2.6),
        "04_printed_lowlight_noisy.jpg": _photograph(
            printed, angle=3.0, dark=0.45, noise=220_000),
        # Handwritten notes, increasingly hostile.
        "05_handwritten_neat.jpg": _photograph(
            _paper(HANDWRITTEN_MEDS, _font(_HAND_FONTS["neat"], 40), 62),
            angle=2.5),
        "06_handwritten_messy.jpg": _photograph(
            _paper(HANDWRITTEN_MESSY, _font(_HAND_FONTS["messy"], 42), 88,
                   jitter=40, rng=rng),
            angle=-4.0, shadow=True),
        "07_handwritten_blurred.jpg": _photograph(
            _paper(HANDWRITTEN_MEDS, _font(_HAND_FONTS["note"], 42), 66),
            angle=3.5, blur=2.2, dark=0.75),
    }

    # Mixed form: printed labels, handwritten fill-ins.
    form = Image.new("RGB", (PAPER_W, PAPER_H), (252, 251, 247))
    fdraw = ImageDraw.Draw(form)
    label_font = _font(_PRINT_FONTS, 30)
    hand_font = _font(_HAND_FONTS["neat"], 40)
    fdraw.text((70, 60), "MERCY GENERAL - DISCHARGE WORKSHEET",
               font=_font(_PRINT_FONTS, 34), fill=(30, 30, 35))
    y = 200
    for label, fill in MIXED_FORM_FILLS:
        fdraw.text((70, y), label, font=label_font, fill=(30, 30, 35))
        fdraw.line((70, y + 90, PAPER_W - 90, y + 90), fill=(120, 120, 130), width=2)
        fdraw.text((420, y + 8), fill, font=hand_font, fill=(25, 25, 90))
        y += 180
    fdraw.text((70, y + 40),
               "WARNING SIGNS: severe trouble breathing, chest pain,\n"
               "fainting - CALL 911. Weight gain over 3 lbs/day - call doctor.",
               font=label_font, fill=(30, 30, 35))
    tiers["08_mixed_form.jpg"] = _photograph(form, angle=-2.2, shadow=True)

    for name, img in tiers.items():
        img.save(OUT_DIR / name, quality=88)
        print(f"wrote {OUT_DIR / name}")


if __name__ == "__main__":
    main()
