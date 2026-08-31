#!/usr/bin/env python3
"""
scripts/build_fax_stratum.py

Creates a degraded "scanned or faxed" stratum from existing corpus documents,
so extraction accuracy can be measured on the format the product's design
centre actually exists for. Owner: Likitha Shankar.

Dr. Liebovitz, review item 3.3, and the LOF review on 26 Aug 2026: test across
structured EHR exports through to low-quality scans and faxes, and report
accuracy PER STRATUM. Today the corpus is 106 MTSamples documents, every one of
them dictated prose, so every accuracy figure the project quotes generalises
only to that one format.

WHAT THIS IS AND IS NOT
-----------------------
This SIMULATES OCR damage on text that was already extracted cleanly. It is not
a real fax and not a real scan, and it must never be described as one. Real
scanning adds skew, speckle, dropped lines and column-merge errors that a text
transform cannot reproduce.

What it does give is a lower bound. If extraction degrades on documents whose
CONTENT is known to be identical to the clean original, the degradation is
attributable to the noise rather than to the document, which is precisely the
comparison a per-stratum accuracy table needs. Real scans remain the better
test and are worth acquiring; this exists so the stratum is not empty while
that is arranged.

Degradations applied are drawn from what OCR actually gets wrong on faxed
clinical documents: character confusion, spacing damage, and dropped
punctuation.

Usage:
    python scripts/build_fax_stratum.py --limit 10
    python scripts/build_fax_stratum.py --severity heavy --out-dir test-data/fax

Deterministic: the same document always degrades the same way, so a re-run does
not silently change what a measurement was taken against.
"""

import argparse
import hashlib
import logging
import random
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Character confusions an OCR engine genuinely makes on faxed text. Digits and
# letters that share a glyph shape dominate.
_CONFUSIONS = {
    "l": "1", "I": "1", "1": "l",
    "O": "0", "0": "O", "o": "0",
    "S": "5", "5": "S",
    "B": "8", "8": "B",
    "Z": "2", "2": "Z",
    "rn": "m", "cl": "d", "vv": "w",
}

_SEVERITY = {
    # Fraction of eligible characters touched. "light" is a good fax; "heavy"
    # is a third-generation photocopy faxed twice.
    "light": 0.010,
    "medium": 0.030,
    "heavy": 0.060,
}


def _degrade(text: str, rate: float, seed: int) -> str:
    """
    Apply deterministic OCR-style damage to document text.

    Args:
        text: Clean extracted text.
        rate: Fraction of characters eligible for corruption.
        seed: Per-document seed, so output is reproducible.

    Returns:
        The degraded text.

    Note:
        Digits inside what look like doses are corrupted at a REDUCED rate.
        Real OCR does misread doses, and that is the most dangerous failure
        the pipeline can face - but corrupting them at the full rate would
        make the stratum measure arithmetic rather than extraction, and every
        document would fail for the same uninteresting reason.
    """
    rng = random.Random(seed)
    out = []
    for line in text.splitlines():
        chars = list(line)
        for i, ch in enumerate(chars):
            if not ch.strip():
                continue
            # Dose-like context: a digit adjacent to another digit or a unit.
            near = line[max(0, i - 3):i + 4].lower()
            dose_like = ch.isdigit() and any(
                u in near for u in ("mg", "ml", "mcg", "unit", "%")
            )
            effective = rate * 0.25 if dose_like else rate
            if rng.random() >= effective:
                continue
            if ch in _CONFUSIONS:
                chars[i] = _CONFUSIONS[ch]
            elif rng.random() < 0.5:
                chars[i] = ch + " "          # spacing damage
            else:
                chars[i] = ""                 # dropped character
        degraded = "".join(chars)
        # Fax headers and edge artefacts land on their own lines.
        if rng.random() < rate * 2:
            degraded = degraded + "  |"
        out.append(degraded)
    return "\n".join(out)


def build(source_dir: Path, out_dir: Path, severity: str, limit: int | None) -> int:
    """
    Render degraded copies of corpus PDFs into a new stratum directory.

    Args:
        source_dir: Directory of clean source PDFs.
        out_dir: Where to write the degraded PDFs.
        severity: One of light, medium, heavy.
        limit: Maximum documents to convert.

    Returns:
        Number of documents written.
    """
    import pdfplumber
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    rate = _SEVERITY[severity]
    out_dir.mkdir(parents=True, exist_ok=True)
    style = getSampleStyleSheet()["BodyText"]
    written = 0

    for pdf in sorted(source_dir.glob("*.pdf")):
        if limit is not None and written >= limit:
            break
        try:
            with pdfplumber.open(pdf) as doc:
                text = "\n".join((p.extract_text() or "") for p in doc.pages)
        except Exception as exc:  # noqa: BLE001 - skip unreadable sources
            logger.warning("skipping %s: %s", pdf.name, exc)
            continue
        if not text.strip():
            continue

        # Seed from the filename so a re-run reproduces the same corruption.
        seed = int(hashlib.sha256(pdf.stem.encode()).hexdigest()[:8], 16)
        degraded = _degrade(text, rate, seed)

        target = out_dir / f"{pdf.stem}_fax.pdf"
        story = [
            Paragraph(re.sub(r"[<>&]", " ", line), style)
            for line in degraded.splitlines() if line.strip()
        ]
        SimpleDocTemplate(str(target), pagesize=letter).build(story)
        written += 1
        logger.info("%s -> %s", pdf.name, target.name)

    return written


def main() -> None:
    """Build the fax stratum and report how it classifies."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=_REPO / "test-data" / "mtsamples")
    parser.add_argument("--out-dir", type=Path,
                        default=_REPO / "test-data" / "fax")
    parser.add_argument("--severity", choices=sorted(_SEVERITY), default="medium")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    written = build(args.source, args.out_dir, args.severity, args.limit)
    print(f"wrote {written} degraded documents to {args.out_dir}")

    # Verify the stratum actually reads as scanned. A degraded corpus that
    # still classifies as dictated has not created a stratum, it has just
    # made a mess, and reporting on it would be meaningless.
    from dischargeiq.utils.strata import stratum_of_file
    from collections import Counter

    counts = Counter(stratum_of_file(p).value for p in sorted(args.out_dir.glob("*.pdf")))
    print("classified as:", dict(counts))
    if counts.get("scanned", 0) < written:
        print("WARNING: not every document reads as scanned. Either raise "
              "--severity or the OCR-noise threshold in utils/strata.py is "
              "mis-calibrated. Do NOT report these as a scanned stratum until "
              "they classify as one.")


if __name__ == "__main__":
    main()
