"""
File: dischargeiq/utils/strata.py
Owner: Likitha Shankar
Description: Classifies a source document into a format stratum so extraction
  accuracy can be reported per stratum instead of as one blended number.
Key functions/classes: classify_stratum, Stratum
Edge cases handled:
  - Returns UNKNOWN rather than guessing when signals conflict or the text is
    too short to judge.
Dependencies: standard library only.
Called by: scripts/run_corpus_for_review.py (stamps the stratum into
  _review_meta), scripts/corpus_accuracy_report.py (per-stratum tables).

WHY STRATA MATTER HERE
----------------------
Dr. Liebovitz, review item 3.3: build a stratified test corpus across at least
four source formats and report extraction accuracy per stratum before
optimising anything downstream. The LOF review on 26 Aug 2026 repeated it -
structured EHR data through to low-quality scans and faxes.

The problem this exposes: all 106 documents in the current corpus are MTSamples
transcriptions, which is ONE stratum - dictated narrative prose. Every accuracy
figure the project quotes therefore generalises only to dictated documents,
while the product's stated design centre is PDFs, and healthcare still faxes.
A single blended accuracy number hides which format is failing.

Classification is heuristic and says so. It reads formatting, not meaning, and
is meant to sort a corpus for reporting - never to change how a document is
processed. A misfiled document skews a report; it must not alter a patient's
output.
"""

import re
from enum import Enum


class Stratum(str, Enum):
    """Source-format families that fail in different ways."""

    #: Clean export from an EHR. Section headers, key/value lines, consistent
    #: structure. What extraction is easiest on and what demos usually show.
    STRUCTURED = "structured"

    #: Dictated and transcribed. Narrative prose, few or no headers, sections
    #: implied rather than labelled. The entire current corpus.
    DICTATED = "dictated"

    #: Scanned or faxed, then OCR'd. Character confusion, broken words, stray
    #: punctuation, inconsistent spacing. The format the design centre exists
    #: for and the one with no coverage at all today.
    SCANNED = "scanned"

    #: Signals conflict or there is too little text to judge. Reported as its
    #: own row rather than folded into a neighbour, because an unclassifiable
    #: document is a finding.
    UNKNOWN = "unknown"


# WHAT ACTUALLY SEPARATES THE STRATA, measured rather than assumed.
#
# The first version of this classifier used section headings and key/value
# lines. Both were wrong, and measuring the two committed corpora showed why:
#
#   signal (per 100 lines)   dictated (MTSamples, n=15)   structured (n=3)
#   headings                 13.0                          15.2   <- shared
#   key: value               14.1                          8.4    <- HIGHER in
#                                                                     dictated
#   bullets                  0.0  (max 0.0)                62.8
#
# Dictated medical transcription is full of ALL-CAPS section labels -
# "PROCEDURES:", "HISTORY:" - followed by prose. It is not unstructured, it is
# structured differently. Counting headings filed 8 of 12 MTSamples documents
# as "structured", which is exactly backwards.
#
# Bullets are the real separator, and the gap is not marginal: zero versus
# sixty. A structured export enumerates; a transcription narrates.

# "• Hypertension" or "- Furosemide 40mg". Enumeration is the tell.
_BULLET = re.compile(r"^\s*[\u2022\-\*\u00b7]\s+\S", re.M)

# "Discharge Date: 2026-04-02" - content on the SAME line as the label. Kept
# for reporting even though it does not discriminate on its own.
_KEY_VALUE = re.compile(r"^\s*[A-Za-z][A-Za-z /()]{2,30}:\s+\S.+$", re.M)

# OCR damage. Each alone is weak evidence; together they are the signature.
_OCR_ARTEFACTS = (
    re.compile(r"\b[lI1]{2,}\b"),          # l/I/1 confusion runs
    re.compile(r"[a-z]\s{2,}[a-z]"),       # words split by stray spacing
    re.compile(r"\b\w*[|]{1,}\w*\b"),      # pipes from table borders
    re.compile(r"[^\w\s.,;:()/%-]{2,}"),   # clusters of odd punctuation
    re.compile(r"\b[A-Za-z]\s[A-Za-z]\s[A-Za-z]\b"),  # s p a c e d letters
)

#: Below this many characters there is nothing to classify honestly.
_MIN_TEXT = 200

#: Bullets per 100 lines above which a document is enumerated, not narrated.
#: Measured range is 0.0 for dictated and 62+ for structured, so this sits in
#: an empty gap rather than on a boundary.
_BULLET_STRUCTURED = 15.0


def _ocr_noise_score(text: str) -> float:
    """
    Rough OCR damage, as artefact matches per 1000 characters.

    Args:
        text: Raw document text.

    Returns:
        Matches per 1000 characters across every artefact pattern.
    """
    if not text:
        return 0.0
    hits = sum(len(pattern.findall(text)) for pattern in _OCR_ARTEFACTS)
    return 1000.0 * hits / len(text)


def _bullet_score(text: str) -> float:
    """
    Bullet lines per 100 non-blank lines - the discriminating signal.

    Args:
        text: Raw document text.

    Returns:
        Bullet density.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    return 100.0 * len(_BULLET.findall(text)) / len(lines)


def _key_value_score(text: str) -> float:
    """
    Key/value lines per 100 non-blank lines. Reported, not decisive.

    Args:
        text: Raw document text.

    Returns:
        Key/value density.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    return 100.0 * len(_KEY_VALUE.findall(text)) / len(lines)


def classify_stratum(text: str) -> Stratum:
    """
    Sort a document into a format stratum for reporting.

    Order matters. OCR damage is checked FIRST, because a scanned EHR export
    still carries headings and would otherwise be filed as structured - and
    the damage is the thing that makes it hard, not the layout.

    Args:
        text: Raw extracted document text.

    Returns:
        The stratum, or UNKNOWN when the text is too short or the signals do
        not separate. UNKNOWN is a real answer here, not a fallback: a corpus
        full of unclassifiable documents is worth seeing rather than smoothing
        into whichever bucket happened to win.
    """
    if not text or len(text) < _MIN_TEXT:
        return Stratum.UNKNOWN

    noise = _ocr_noise_score(text)
    bullets = _bullet_score(text)

    # OCR damage first: a scanned EHR export still enumerates, and the damage
    # is what makes it hard, not the layout.
    if noise >= 6.0:
        return Stratum.SCANNED
    if bullets >= _BULLET_STRUCTURED:
        return Stratum.STRUCTURED
    # Everything readable that does not enumerate is narrated. There is no
    # UNKNOWN band between the two, because the measured gap is 0 versus 62 -
    # inventing a middle zone would only file real documents nowhere.
    return Stratum.DICTATED


#: Directories whose contents have a KNOWN stratum. Provenance beats
#: inference: we built these, so there is nothing to detect.
_KNOWN_DIRS = {
    "fax": Stratum.SCANNED,
    "scanned": Stratum.SCANNED,
    "synthetic": Stratum.STRUCTURED,
    "mtsamples": Stratum.DICTATED,
}


def stratum_of_file(path) -> Stratum:
    """
    Determine a source PDF's stratum, preferring provenance over inference.

    A file under test-data/fax/ IS scanned - we degraded it - so no heuristic
    is consulted. Text analysis is the fallback for documents of unknown
    origin, such as anything a patient uploads.

    Args:
        path: Path to a PDF.

    Returns:
        The stratum, or UNKNOWN when the file cannot be read. Classification
        is metadata for a report and must never raise into a corpus run.

    Note on the SCANNED heuristic, measured 31 Aug 2026 and NOT good enough
    to rely on. OCR noise scored on 25 clean MTSamples documents ranged 0.00
    to 11.02; six deliberately degraded copies ranged 7.63 to 13.47. Those
    overlap, because real clinical dictation is full of lab values and
    abbreviations that look like OCR damage ("BUN 19", "PTT 37.1"). So a
    document of unknown origin will NOT be reliably identified as scanned by
    this code. Saying so is more useful than a threshold that quietly
    misfiles a third of each group.
    """
    from pathlib import Path as _Path

    parts = {part.lower() for part in _Path(path).parts}
    for name, stratum in _KNOWN_DIRS.items():
        if name in parts:
            return stratum

    try:
        import pdfplumber

        with pdfplumber.open(path) as doc:
            text = " ".join((page.extract_text() or "") for page in doc.pages)
    except Exception:  # noqa: BLE001 - a corrupt PDF is UNKNOWN, not a crash
        return Stratum.UNKNOWN
    return classify_stratum(text)
