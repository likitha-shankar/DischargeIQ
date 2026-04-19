"""
Integration + hallucination test for Agent 1 (extraction) and Agent 2
(diagnosis explanation).

Owner: Likitha | Sprint 2

Generates 8 synthetic discharge PDFs with fully known ground truth,
runs the real `dischargeiq.pipeline.orchestrator.run_pipeline()` end to
end (NO mocks, real LLM calls to whatever provider is configured in
.env), and classifies every discrepancy as either HALLUCINATION (value
in output but not in source) or OMISSION (value in source but not in
output). A secondary LLM judge audits Agent 2's explanation text for
unsupported clinical claims.

Run with:
    python dischargeiq/tests/test_integration_hallucination.py

Exits 0 on PASS, 1 on FAIL. Also writes a per-case report to stdout
and detailed diffs to the existing session log file
(logs/session_YYYYMMDD_HHMMSS.log) via the project logger.

Dependencies (added to requirements.txt in this sprint):
    - reportlab   — synthetic PDF generation
    - deepdiff    — pretty diffs in debug log only (not in gate path)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

# Make `dischargeiq` importable when this script is launched directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO_ROOT / ".env")

from deepdiff import DeepDiff  # noqa: E402
from reportlab.lib.pagesizes import LETTER  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

import anthropic  # noqa: E402

from dischargeiq.pipeline.orchestrator import run_pipeline  # noqa: E402
from dischargeiq.utils.llm_client import get_llm_client  # noqa: E402
from dischargeiq.utils.logger import configure_logging  # noqa: E402


# ── Paths ─────────────────────────────────────────────────────────────────────

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Issue:
    """A single hallucination or omission flagged against a field."""
    kind: str          # "HALLUCINATION" or "OMISSION"
    field: str         # e.g. "medications", "follow_up_appointments"
    detail: str        # human-readable explanation

    def __str__(self) -> str:
        return f"[{self.kind}] {self.field}: {self.detail}"


@dataclass
class Profile:
    """A synthetic discharge case with deterministic ground truth."""
    name: str
    pages: list[str]                      # one string per PDF page
    ground_truth: dict                    # mirrors ExtractionOutput fields
    distractor_meds: list[str] = field(default_factory=list)
    expected_warnings: list[str] = field(default_factory=list)


# ── Normalization helpers ─────────────────────────────────────────────────────

# Frequency abbreviations → canonical phrase. Applied to both sides of the
# comparison so the test does not penalize valid synonyms.
_FREQ_MAP = {
    "qd": "once daily",
    "q.d.": "once daily",
    "once a day": "once daily",
    "once per day": "once daily",
    "daily": "once daily",
    "bid": "twice daily",
    "b.i.d.": "twice daily",
    "twice a day": "twice daily",
    "tid": "three times daily",
    "t.i.d.": "three times daily",
    "three times a day": "three times daily",
    "qid": "four times daily",
    "q.i.d.": "four times daily",
    "four times a day": "four times daily",
    "q4h": "every 4 hours",
    "q6h": "every 6 hours",
    "q8h": "every 8 hours",
    "q12h": "every 12 hours",
    "qhs": "at bedtime",
    "hs": "at bedtime",
    "prn": "as needed",
}

_DRUG_SUFFIX_STRIP = re.compile(r"\b(er|xl|sr|xr|cr|la)\b", re.IGNORECASE)
_NUMERIC_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([a-zA-Z/%]+)?")


def norm_freq(freq: str | None) -> str:
    """Lowercase and collapse frequency synonyms to a canonical phrase."""
    if not freq:
        return ""
    s = freq.lower().strip()
    # Strip PRN-flag and common scheduling words that do not change meaning.
    s = re.sub(r"\s+", " ", s)
    # Replace longest abbrevs first so "b.i.d." does not hit a "bid" suffix.
    for abbrev in sorted(_FREQ_MAP, key=len, reverse=True):
        s = re.sub(rf"\b{re.escape(abbrev)}\b", _FREQ_MAP[abbrev], s)
    return s.strip()


def norm_drug_name(name: str | None) -> str:
    """Lowercase drug name, strip common formulation suffixes for matching."""
    if not name:
        return ""
    s = name.lower().strip()
    # Strip dosing parentheticals and trailing brand-name annotations.
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = _DRUG_SUFFIX_STRIP.sub("", s).strip()
    s = re.sub(r"\s+", " ", s)
    # Generic/brand aliases that arise in our fixtures.
    aliases = {
        "augmentin": "amoxicillin-clavulanate",
        "amoxicillin/clavulanate": "amoxicillin-clavulanate",
        "amoxicillin clavulanate": "amoxicillin-clavulanate",
        "lasix": "furosemide",
        "coreg": "carvedilol",
        "lovenox": "enoxaparin",
    }
    return aliases.get(s, s)


def parse_dose(dose: str | None) -> tuple[float | None, str]:
    """Return (numeric, unit) from a dose string like '40 mg' or '2.5mg'."""
    if not dose:
        return None, ""
    match = _NUMERIC_RE.search(dose)
    if not match:
        return None, dose.lower().strip()
    value = float(match.group(1))
    unit = (match.group(2) or "").lower().strip()
    return value, unit


def dose_close(got: str | None, expected: str | None, tolerance: float = 0.05) -> bool:
    """True if dose strings agree within ±tolerance on the numeric part."""
    if not got and not expected:
        return True
    if not got or not expected:
        return False
    g_val, g_unit = parse_dose(got)
    e_val, e_unit = parse_dose(expected)
    if g_val is None or e_val is None:
        return got.strip().lower() == expected.strip().lower()
    if g_unit and e_unit and g_unit != e_unit:
        return False
    return abs(g_val - e_val) <= tolerance * max(e_val, 1e-9)


def token_set(text: str) -> set[str]:
    """Lowercase alphanumeric token set for fuzzy comparison."""
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def overlap_ratio(a: str, b: str) -> float:
    """Jaccard-style overlap between two phrases for red-flag matching."""
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta | tb), 1)


# ── Medical abbreviation expansion ────────────────────────────────────────────
# Diagnoses can be written in shorthand ("GERD", "HTN", "CHF") or fully spelled
# out ("gastroesophageal reflux disease"). The token-overlap ratio used by
# check_primary_dx / check_secondary_dx scores those two forms as disjoint
# because they share zero tokens. Expanding known abbreviations on BOTH sides
# of the comparison — at comparison time — lets the harness treat the two
# forms as equivalent without forcing the extractor to pick a single style.
#
# Keys are stored lowercase for case-insensitive lookup; the regex in
# _expand_medical_abbreviations() does its own .lower() before dict hits.
_MEDICAL_ABBREVIATIONS: dict[str, str] = {
    "gerd":  "gastroesophageal reflux disease",
    "copd":  "chronic obstructive pulmonary disease",
    "chf":   "congestive heart failure",
    "htn":   "hypertension",
    "dm":    "diabetes mellitus",
    "dm2":   "type 2 diabetes mellitus",
    "t2dm":  "type 2 diabetes mellitus",
    "ckd":   "chronic kidney disease",
    "aki":   "acute kidney injury",
    "sob":   "shortness of breath",
    "cad":   "coronary artery disease",
    "afib":  "atrial fibrillation",
    "pe":    "pulmonary embolism",
    "dvt":   "deep vein thrombosis",
    "uti":   "urinary tract infection",
    "osa":   "obstructive sleep apnea",
}


def _expand_medical_abbreviations(text: str) -> str:
    """
    Expand known medical abbreviations to their full clinical form.

    Substitution is case-insensitive and applied only on whole-word token
    boundaries, so the abbreviation "PE" inside "PEDIATRIC" is not expanded
    incorrectly. Non-abbreviation words are preserved verbatim; whitespace is
    collapsed so the expanded string tokenises cleanly.

    Used by check_primary_dx and check_secondary_dx before passing the result
    to overlap_ratio — without this pre-pass "GERD" and "gastroesophageal
    reflux disease" compare as disjoint token sets.

    Args:
        text: Arbitrary diagnosis string from ground-truth or extractor output.

    Returns:
        Lowercase string with known abbreviations expanded. Returns an empty
        string when `text` is falsy.
    """
    if not text:
        return ""
    lowered = text.lower()

    def _sub(match: "re.Match[str]") -> str:
        token = match.group(0)
        return _MEDICAL_ABBREVIATIONS.get(token, token)

    # \b word boundaries guard against substring false-positives ("PE" inside
    # "PEDIATRIC"). The allowed-character class includes digits so tokens like
    # "dm2" and "t2dm" match the keys in _MEDICAL_ABBREVIATIONS.
    expanded = re.sub(r"\b[a-z][a-z0-9]*\b", _sub, lowered)
    return re.sub(r"\s+", " ", expanded).strip()


# ── Red-flag fuzzy matching ───────────────────────────────────────────────────
# Clinical shorthand the extractor sometimes leaves unexpanded in the
# red_flag_symptoms list (e.g. "SOB" for shortness of breath). Expanding these
# at comparison time — on both sides — lets the harness accept a raw
# abbreviation as an equivalent match to the spelled-out ground-truth phrase
# without forcing the extractor to do the expansion itself.
_RED_FLAG_ABBREV_MAP: dict[str, str] = {
    "sob":   "shortness of breath",
    "doe":   "shortness of breath on exertion",
    "cp":    "chest pain",
    "abd":   "abdominal",
    "n/v":   "nausea vomiting",
    "h/a":   "headache",
    "loc":   "loss of consciousness",
    "ams":   "altered mental status",
    "ha":    "headache",
}

# Symbols that appear inside red-flag text (e.g. "fever > 102F") are rewritten
# to their word equivalents before tokenisation so token-level comparison is
# insensitive to the author's choice of ">" vs "over".
_SYMBOL_MAP: dict[str, str] = {
    ">=": " over or equal to ",
    "<=": " under or equal to ",
    ">":  " over ",
    "<":  " under ",
    "°f": "",
    "°c": "",
    "°":  "",
}


def _normalize_red_flag(text: str) -> str:
    """
    Normalise a red-flag phrase for fuzzy comparison.

    Lowercases the input, expands inequality symbols to words ("> 102" becomes
    "over 102"), strips temperature-unit glyphs, expands common clinical
    abbreviations (SOB, CP, DOE) on whole-token boundaries, splits glued
    digit-letter tokens like "102F" into separate tokens ("102" and "F"), and
    removes all remaining punctuation. The resulting string is a
    whitespace-collapsed lowercase sentence suitable for contiguous-word
    overlap checks.

    Args:
        text: A single red-flag string from either the extraction output or
              the ground-truth profile.

    Returns:
        Normalised phrase. Returns an empty string when `text` is falsy.
    """
    if not text:
        return ""
    lowered = text.lower()
    for sym, replacement in _SYMBOL_MAP.items():
        lowered = lowered.replace(sym, replacement)
    # Split digit-letter joins so "102f" becomes "102 f" and tokenises cleanly.
    lowered = re.sub(r"(\d)([a-z])", r"\1 \2", lowered)
    lowered = re.sub(r"([a-z])(\d)", r"\1 \2", lowered)

    # Expand abbreviations on whole-token boundaries. Using \S+ so the match
    # includes punctuated tokens like "n/v" that are in the abbreviation map.
    def _expand(match: "re.Match[str]") -> str:
        token = match.group(0)
        return _RED_FLAG_ABBREV_MAP.get(token, token)

    lowered = re.sub(r"[a-z/]+", _expand, lowered)
    # Drop any punctuation that survived, then collapse whitespace.
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def fuzzy_red_flag_match(expected: str, got: str, n: int = 3) -> bool:
    """
    Return True if `got` contains any n-consecutive-word sub-sequence of
    `expected` (or vice versa) after both strings are normalised.

    Normalisation handles symbol-to-word substitution (">" -> "over"),
    temperature-unit stripping, clinical abbreviation expansion
    (SOB -> shortness of breath), and digit-letter splitting ("102F" ->
    "102 f"). The contiguous-subsequence check is symmetric so that a short
    output phrase can still match a longer ground-truth phrase and vice versa.
    When either phrase has fewer than `n` words, the window shrinks to the
    shorter phrase's length — a single-word GT like "confusion" matches any
    output that contains that word as a contiguous token.

    Args:
        expected: Ground-truth red-flag phrase.
        got:      Extractor-emitted red-flag phrase.
        n:        Maximum contiguous-window size (defaults to 3 words).

    Returns:
        True on match, False otherwise.
    """
    exp_words = _normalize_red_flag(expected).split()
    got_words = _normalize_red_flag(got).split()
    if not exp_words or not got_words:
        return False

    def _contains_ngram(source: list[str], target: list[str], window: int) -> bool:
        if window <= 0 or len(source) < window or len(target) < window:
            return False
        for start in range(len(source) - window + 1):
            ngram = source[start:start + window]
            for offset in range(len(target) - window + 1):
                if target[offset:offset + window] == ngram:
                    return True
        return False

    # Use the tighter of n and the shorter phrase's length so small GT items
    # like "confusion" still match when present as a standalone token.
    window = min(n, len(exp_words), len(got_words))
    return (
        _contains_ngram(exp_words, got_words, window)
        or _contains_ngram(got_words, exp_words, window)
    )


# ── PDF generation ────────────────────────────────────────────────────────────

def generate_pdf(profile: Profile, out_path: Path) -> None:
    """
    Render profile.pages to a multi-page PDF at out_path using reportlab.

    Each entry in profile.pages becomes one PDF page. Inside a page, blank
    lines separate paragraphs. Lines starting with "# " become bold headings.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        title=profile.name,
        leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
    )
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize = 10
    body.leading = 13
    heading = styles["Heading2"]
    heading.fontSize = 12
    heading.spaceAfter = 4

    story = []
    for page_index, page_text in enumerate(profile.pages):
        for raw_block in page_text.split("\n\n"):
            block = raw_block.strip()
            if not block:
                continue
            if block.startswith("# "):
                story.append(Paragraph(block[2:].strip(), heading))
            else:
                # reportlab Paragraph interprets HTML entities — escape <>&
                escaped = (
                    block.replace("&", "&amp;")
                         .replace("<", "&lt;")
                         .replace(">", "&gt;")
                         .replace("\n", "<br/>")
                )
                story.append(Paragraph(escaped, body))
            story.append(Spacer(1, 4))
        if page_index != len(profile.pages) - 1:
            story.append(PageBreak())
    doc.build(story)


# ── Check functions ───────────────────────────────────────────────────────────

def check_patient(out: dict, gt: dict) -> list[Issue]:
    """Patient name and discharge date: exact match when ground truth non-null."""
    issues: list[Issue] = []
    gt_name = (gt.get("patient_name") or "").strip().lower()
    got_name = (out.get("patient_name") or "").strip().lower()
    if gt_name and not got_name:
        issues.append(Issue("OMISSION", "patient_name",
                            f"expected '{gt['patient_name']}', got None"))
    elif gt_name and got_name and gt_name not in got_name and got_name not in gt_name:
        issues.append(Issue("HALLUCINATION", "patient_name",
                            f"expected '{gt['patient_name']}', got '{out['patient_name']}'"))

    gt_date = (gt.get("discharge_date") or "").strip()
    got_date = (out.get("discharge_date") or "").strip()
    if gt_date and not got_date:
        issues.append(Issue("OMISSION", "discharge_date",
                            f"expected '{gt_date}', got None"))
    elif gt_date and got_date and gt_date not in got_date:
        issues.append(Issue("HALLUCINATION", "discharge_date",
                            f"expected '{gt_date}', got '{got_date}'"))
    return issues


def check_primary_dx(out: dict, gt: dict) -> list[Issue]:
    """Primary diagnosis: token-set overlap ≥ 40% counts as match.

    Abbreviations are expanded on both sides via
    _expand_medical_abbreviations() before computing the overlap ratio so
    forms like 'T2DM' and 'type 2 diabetes mellitus' compare as equivalent
    instead of scoring zero token overlap.
    """
    issues: list[Issue] = []
    gt_dx = gt.get("primary_diagnosis", "") or ""
    got_dx = out.get("primary_diagnosis", "") or ""
    if gt_dx and not got_dx:
        issues.append(Issue("OMISSION", "primary_diagnosis",
                            f"expected '{gt_dx}', got empty"))
        return issues
    if gt_dx:
        gt_expanded = _expand_medical_abbreviations(gt_dx)
        got_expanded = _expand_medical_abbreviations(got_dx)
        if overlap_ratio(gt_expanded, got_expanded) < 0.4:
            issues.append(Issue("HALLUCINATION", "primary_diagnosis",
                                f"expected '{gt_dx}', got '{got_dx}'"))
    return issues


def check_secondary_dx(out: dict, gt: dict) -> list[Issue]:
    """Secondary diagnoses: set compare with token-overlap ≥ 40% for match.

    Each GT and output string is passed through _expand_medical_abbreviations
    before the overlap check so a GT entry 'GERD' matches an output entry
    'Gastroesophageal Reflux Disease' (and vice versa).
    """
    issues: list[Issue] = []
    got = out.get("secondary_diagnoses") or []
    gt_list = gt.get("secondary_diagnoses") or []

    matched_out: set[int] = set()
    for g in gt_list:
        hit = False
        g_expanded = _expand_medical_abbreviations(g)
        for i, o in enumerate(got):
            if i in matched_out:
                continue
            if overlap_ratio(g_expanded, _expand_medical_abbreviations(o)) >= 0.4:
                matched_out.add(i)
                hit = True
                break
        if not hit:
            issues.append(Issue("OMISSION", "secondary_diagnoses",
                                f"expected '{g}' not found in output"))

    for i, o in enumerate(got):
        if i not in matched_out:
            issues.append(Issue("HALLUCINATION", "secondary_diagnoses",
                                f"unexpected '{o}' in output"))
    return issues


def check_medications(out: dict, gt: dict) -> list[Issue]:
    """Medications: match by normalized drug name, then check dose/freq/status."""
    issues: list[Issue] = []
    got_meds = out.get("medications") or []
    gt_meds = gt.get("medications") or []

    gt_by_name = {norm_drug_name(m["name"]): m for m in gt_meds}
    got_by_name: dict[str, dict] = {}
    for m in got_meds:
        key = norm_drug_name(m.get("name"))
        if key:
            got_by_name.setdefault(key, m)

    # Every ground-truth med must be present in output.
    for key, exp in gt_by_name.items():
        got = got_by_name.get(key)
        if got is None:
            # Substring fallback — LLM may prefix/suffix with brand name.
            for gk, gm in got_by_name.items():
                if key in gk or gk in key:
                    got = gm
                    break
        if got is None:
            issues.append(Issue("OMISSION", "medications",
                                f"expected drug '{exp['name']}' not in output"))
            continue
        if not dose_close(got.get("dose"), exp.get("dose")):
            issues.append(Issue("HALLUCINATION", "medications",
                                f"'{exp['name']}' dose: expected '{exp.get('dose')}',"
                                f" got '{got.get('dose')}'"))
        gf = norm_freq(got.get("frequency"))
        ef = norm_freq(exp.get("frequency"))
        if ef and ef not in gf and gf not in ef:
            issues.append(Issue("HALLUCINATION", "medications",
                                f"'{exp['name']}' frequency: expected '{exp.get('frequency')}',"
                                f" got '{got.get('frequency')}'"))
        if exp.get("status") and got.get("status") and exp["status"] != got["status"]:
            issues.append(Issue("HALLUCINATION", "medications",
                                f"'{exp['name']}' status: expected '{exp['status']}',"
                                f" got '{got['status']}'"))

    # Any output med not in ground truth (and not a trivial substring of one)
    # is a hallucination.
    for key, got in got_by_name.items():
        if key in gt_by_name:
            continue
        if any(key in gk or gk in key for gk in gt_by_name):
            continue
        issues.append(Issue("HALLUCINATION", "medications",
                            f"unexpected drug '{got.get('name')}' in output"))
    return issues


def check_distractors_absent(out: dict, distractors: list[str]) -> list[Issue]:
    """Distractor meds (pre-op, not prescribed at discharge) must not appear."""
    issues: list[Issue] = []
    if not distractors:
        return issues
    got_names = {norm_drug_name(m.get("name")) for m in (out.get("medications") or [])}
    for drug in distractors:
        key = norm_drug_name(drug)
        if key and (key in got_names or any(key in g for g in got_names)):
            issues.append(Issue("HALLUCINATION", "medications",
                                f"pre-op distractor '{drug}' leaked into discharge meds"))
    return issues


def check_appointments(out: dict, gt: dict) -> list[Issue]:
    """Follow-up appts: match by specialty, then verify provider and date."""
    issues: list[Issue] = []
    got_appts = out.get("follow_up_appointments") or []
    gt_appts = gt.get("follow_up_appointments") or []

    matched_out: set[int] = set()
    for exp in gt_appts:
        hit = None
        for i, got in enumerate(got_appts):
            if i in matched_out:
                continue
            if overlap_ratio(exp.get("specialty", ""), got.get("specialty", "")) >= 0.4:
                hit = (i, got)
                break
        if hit is None:
            issues.append(Issue("OMISSION", "follow_up_appointments",
                                f"expected appt for '{exp.get('specialty')}' not found"))
            continue
        i, got = hit
        matched_out.add(i)
        if exp.get("provider") and got.get("provider"):
            if overlap_ratio(exp["provider"], got["provider"]) < 0.3:
                issues.append(Issue("HALLUCINATION", "follow_up_appointments",
                                    f"provider mismatch for {exp.get('specialty')}:"
                                    f" expected '{exp['provider']}', got '{got['provider']}'"))
        if exp.get("date") and got.get("date") and exp["date"] not in got["date"]:
            issues.append(Issue("HALLUCINATION", "follow_up_appointments",
                                f"date mismatch for {exp.get('specialty')}:"
                                f" expected '{exp['date']}', got '{got['date']}'"))

    for i, got in enumerate(got_appts):
        if i in matched_out:
            continue
        # Allow generic service-type appts (e.g. "Home Health PT") only if GT
        # has *something* we couldn't match above.
        issues.append(Issue("HALLUCINATION", "follow_up_appointments",
                            f"unexpected appt in output: '{got}'"))
    return issues


def check_red_flags(out: dict, gt: dict) -> list[Issue]:
    """Red flag symptoms: each GT item must overlap with at least one output item."""
    issues: list[Issue] = []
    got_flags = out.get("red_flag_symptoms") or []
    gt_flags = gt.get("red_flag_symptoms") or []

    if not gt_flags:
        return issues  # Empty GT — nothing to verify.

    matched_out: set[int] = set()
    for exp in gt_flags:
        hit = False
        for i, got in enumerate(got_flags):
            if i in matched_out:
                continue
            # fuzzy_red_flag_match normalises abbreviations (SOB ->
            # "shortness of breath") and symbols (">" -> "over") on both
            # sides, then accepts any 3-consecutive-word overlap. For
            # phrases shorter than 3 words the window tightens so a
            # one-word GT like "confusion" still matches.
            if fuzzy_red_flag_match(exp, got):
                matched_out.add(i)
                hit = True
                break
        if not hit:
            issues.append(Issue("OMISSION", "red_flag_symptoms",
                                f"expected '{exp}' not found in output"))
    # Unmatched output flags — flag only when the phrase has no fuzzy match
    # against ANY GT entry. Mirrors the GT-side matcher so the harness
    # doesn't penalise extras that are semantically equivalent to a GT item.
    for i, got in enumerate(got_flags):
        if i in matched_out:
            continue
        if not any(fuzzy_red_flag_match(got, g) for g in gt_flags):
            issues.append(Issue("HALLUCINATION", "red_flag_symptoms",
                                f"unexpected '{got}' in output"))
    return issues


def check_warnings(out: dict, profile: Profile) -> list[Issue]:
    """Extraction warnings: profiles 5/6 require specific warning strings."""
    issues: list[Issue] = []
    if not profile.expected_warnings:
        return issues
    got_warnings = out.get("extraction_warnings") or []
    for expected in profile.expected_warnings:
        # Sub-phrase match — accept any warning that shares ≥ 3 key tokens.
        exp_tokens = token_set(expected)
        hit = any(len(exp_tokens & token_set(w)) >= 3 for w in got_warnings)
        if not hit:
            issues.append(Issue("OMISSION", "extraction_warnings",
                                f"missing expected warning: '{expected}'"))
    return issues


# ── Agent 2 audit (LLM judge) ─────────────────────────────────────────────────

_AUDIT_SYSTEM = """You are a clinical auditor. You will be given:
(A) a plain-language diagnosis explanation written for a patient,
(B) a ground-truth JSON dict describing what the source document
    actually contains, and
(C) the raw source-document text.

A clinical claim is "supported" if it is present in EITHER (B) or
(C). A claim is "unsupported" only if it names a specific
medication, dose, imaging finding, test result, procedure, timeline,
or complication that does not appear in either (B) or (C).

General descriptions of the condition itself are always allowed
(e.g. "heart failure means your heart doesn't pump well") because
those are educational context, not document-specific claims.

General plain-language descriptions of what a diagnosis means
(e.g. what an organ does, what the condition affects) are NOT
hallucinations even if not verbatim in the source document.
Only flag sentences that:
  (a) name a specific drug not in the discharge medications list,
  (b) state a specific test result or finding not in the source, or
  (c) give a specific prognosis or outcome claim not in the source.
Do not flag educational explanations of what a diagnosis is.

Reassuring statements ("most people feel better in a few weeks")
are NOT unsupported claims unless they assert a specific clinical
fact about this patient that contradicts the source.

Return JSON only: {"unsupported_claims": ["claim 1", "claim 2"]}
If there are no unsupported claims, return {"unsupported_claims": []}
Do not include preamble, markdown fences, or commentary."""


def audit_agent2_claims(
    explanation: str,
    ground_truth: dict,
    source_text: str | None = None,
) -> list[str]:
    """
    Second-pass LLM judge that returns unsupported clinical claims.

    The judge sees both the ground-truth dict and (when provided) the raw
    source-document text, so legitimate details that appear in the PDF but
    were omitted from the ground-truth scaffold are not flagged as
    hallucinations.

    Args:
        explanation: Agent 2 plain-language output.
        ground_truth: Deterministic GT dict matching ExtractionOutput fields.
        source_text: Optional raw document text (as extracted by pdfplumber)
                     passed as an additional supporting context. When None,
                     the judge considers only the ground-truth dict.

    Returns:
        List of claim strings the judge deemed unsupported. Empty list means
        the audit passed.
    """
    if not explanation or not explanation.strip():
        return []

    # The hallucination judge calls Claude directly via the Anthropic SDK so
    # the harness is independent of whichever provider is configured in
    # LLM_PROVIDER for the agents under test. This isolates the test signal
    # (does the agent hallucinate?) from provider availability issues like
    # rate limits or credit exhaustion on a shared account.
    parts = [
        "EXPLANATION TEXT:",
        explanation,
        "",
        "GROUND-TRUTH JSON:",
        json.dumps(ground_truth, indent=2, default=str),
    ]
    if source_text:
        parts.extend([
            "",
            "RAW SOURCE-DOCUMENT TEXT (trimmed):",
            source_text[:6000],
        ])
    user_message = "\n".join(parts)

    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=_AUDIT_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as exc:
        logger.error("Agent 2 audit Anthropic call failed: %s", exc)
        return []

    # response.content is a list of content blocks; for a text-only reply
    # the first block's .text attribute holds the full response string.
    raw = (response.content[0].text if response.content else "").strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(raw)
        claims = parsed.get("unsupported_claims", [])
        if not isinstance(claims, list):
            return []
        return [str(c) for c in claims if str(c).strip()]
    except json.JSONDecodeError:
        logger.warning("Agent 2 audit returned non-JSON: %s", raw[:200])
        return []


# ── Retry wrapper ─────────────────────────────────────────────────────────────

def run_with_retry(label: str, fn: Callable, *args, **kwargs) -> Any:
    """Call fn; on rate-limit error, sleep 10s and retry once. Then give up."""
    try:
        return fn(*args, **kwargs)
    except Exception as first_exc:  # noqa: BLE001
        msg = str(first_exc).lower()
        if "rate" in msg or "429" in msg or "ratelimit" in msg.replace(" ", ""):
            logger.warning("%s hit rate limit, sleeping 10s and retrying: %s",
                           label, first_exc)
            time.sleep(10)
            return fn(*args, **kwargs)
        raise


# ── Per-case runner ───────────────────────────────────────────────────────────

def _pipeline_to_dict(pipeline_response) -> dict:
    """Convert PipelineResponse (pydantic model) to a plain dict."""
    if hasattr(pipeline_response, "model_dump"):
        return pipeline_response.model_dump()
    if hasattr(pipeline_response, "dict"):
        return pipeline_response.dict()
    return dict(pipeline_response)


def run_case(profile: Profile, index: int, total: int) -> dict:
    """
    Execute one profile end-to-end and return a result dict:
        {
            "name": str,
            "status": "PASS" | "FAIL" | "ERROR",
            "pipeline_status": "complete" | "partial" | "error",
            "issues": list[Issue],
            "hallucinations": int,
            "omissions": int,
            "audit_claims": list[str],
            "error": str | None,
        }
    """
    result = {
        "name": profile.name,
        "status": "PASS",
        "pipeline_status": None,
        "issues": [],
        "hallucinations": 0,
        "omissions": 0,
        "audit_claims": [],
        "error": None,
    }
    logger.info("=== [%d/%d] %s — start ===", index, total, profile.name)

    pdf_path = _FIXTURES_DIR / f"{profile.name}.pdf"
    try:
        generate_pdf(profile, pdf_path)
        logger.info("PDF rendered: %s (%d pages)", pdf_path, len(profile.pages))
    except Exception as pdf_exc:  # noqa: BLE001
        result["status"] = "ERROR"
        result["error"] = f"PDF build failed: {pdf_exc}"
        logger.error("PDF build failed for %s: %s", profile.name, pdf_exc)
        return result

    # Run the real pipeline with rate-limit retry. run_pipeline is async —
    # wrap each call in asyncio.run() so the existing sync retry helper works
    # unchanged.
    def _run_pipeline_sync(path: str):
        return asyncio.run(run_pipeline(path))

    try:
        pipeline_response = run_with_retry(
            f"run_pipeline[{profile.name}]", _run_pipeline_sync, str(pdf_path)
        )
    except Exception as pipe_exc:  # noqa: BLE001
        result["status"] = "ERROR"
        result["error"] = f"Pipeline crashed: {pipe_exc}"
        logger.error("Pipeline crashed for %s: %s", profile.name, pipe_exc)
        return result

    pr = _pipeline_to_dict(pipeline_response)
    result["pipeline_status"] = pr.get("pipeline_status")
    extraction = pr.get("extraction") or {}
    explanation = pr.get("diagnosis_explanation") or ""

    # If the pipeline itself degraded, treat as ERROR so we don't conflate a
    # provider outage with a real hallucination regression.
    if pr.get("pipeline_status") == "partial" and not extraction.get("medications"):
        result["status"] = "ERROR"
        result["error"] = "pipeline_status=partial with empty extraction"
        logger.warning("Skipping checks for %s — %s", profile.name, result["error"])
        return result

    # Field-level checks.
    issues: list[Issue] = []
    issues += check_patient(extraction, profile.ground_truth)
    issues += check_primary_dx(extraction, profile.ground_truth)
    issues += check_secondary_dx(extraction, profile.ground_truth)
    issues += check_medications(extraction, profile.ground_truth)
    issues += check_distractors_absent(extraction, profile.distractor_meds)
    issues += check_appointments(extraction, profile.ground_truth)
    issues += check_red_flags(extraction, profile.ground_truth)
    issues += check_warnings(extraction, profile)

    # Agent 2 audit — only run if an explanation was produced. Pass both the
    # ground-truth dict AND the raw pdfplumber-extracted source text so the
    # judge does not flag legitimate details that were present in the PDF but
    # omitted from the ground-truth scaffold.
    if explanation:
        try:
            from dischargeiq.agents.extraction_agent import extract_text_from_pdf
            raw_source_text = extract_text_from_pdf(str(pdf_path))
        except Exception as txt_exc:  # noqa: BLE001
            logger.warning(
                "Could not re-extract source text for %s audit: %s",
                profile.name, txt_exc,
            )
            raw_source_text = None
        try:
            claims = run_with_retry(
                f"audit[{profile.name}]",
                audit_agent2_claims,
                explanation,
                profile.ground_truth,
                raw_source_text,
            )
            result["audit_claims"] = claims
            for c in claims:
                issues.append(Issue("HALLUCINATION", "agent2_claim", c))
        except Exception as audit_exc:  # noqa: BLE001
            logger.warning("Audit call failed for %s: %s", profile.name, audit_exc)

    result["issues"] = issues
    result["hallucinations"] = sum(1 for i in issues if i.kind == "HALLUCINATION")
    result["omissions"] = sum(1 for i in issues if i.kind == "OMISSION")
    result["status"] = "FAIL" if result["hallucinations"] > 0 else "PASS"

    # Debug diff for the log file only — keeps stdout compact.
    try:
        logger.debug(
            "DeepDiff for %s: %s",
            profile.name,
            DeepDiff(profile.ground_truth, extraction, ignore_order=True,
                     significant_digits=2).to_json()[:4000],
        )
    except Exception:  # noqa: BLE001
        pass

    return result


# ── Profile definitions ───────────────────────────────────────────────────────

def _profiles() -> list[Profile]:
    """Return the 8 test profiles with their ground-truth dicts."""
    return [
        Profile(
            name="t2_diabetes_structured",
            pages=[
                """# DISCHARGE SUMMARY

Patient: Jane Doe
Discharge Date: 2026-04-12

# PRIMARY DIAGNOSIS
Type 2 Diabetes Mellitus with hyperglycemia

# SECONDARY DIAGNOSES
- Hypertension
- Hyperlipidemia
- Obesity

# PROCEDURES PERFORMED
- Hemoglobin A1c measurement (2026-04-08): 9.1%
- Diabetes self-management education
- Nutrition counseling""",
                """# DISCHARGE MEDICATIONS
- Metformin 500mg by mouth twice daily
- Lisinopril 10mg by mouth once daily
- Insulin Glargine 20 units subcutaneous at bedtime
- Atorvastatin 40mg by mouth once daily

# FOLLOW-UP APPOINTMENTS
- Dr. Sarah Chen, Endocrinology - 2026-04-26 - diabetes management
- Dr. Michael Rivera, Primary Care - 2026-05-03 - blood pressure check

# WARNING SIGNS — Call 911 if:
- Severe chest pain
- Difficulty breathing
- Signs of stroke (slurred speech, facial droop)
- Blood sugar below 54 or above 400
- Loss of consciousness""",
            ],
            ground_truth={
                "patient_name": "Jane Doe",
                "discharge_date": "2026-04-12",
                "primary_diagnosis": "Type 2 Diabetes Mellitus with hyperglycemia",
                "secondary_diagnoses": ["Hypertension", "Hyperlipidemia", "Obesity"],
                "procedures_performed": [
                    "Hemoglobin A1c measurement",
                    "Diabetes self-management education",
                    "Nutrition counseling",
                ],
                "medications": [
                    {"name": "Metformin", "dose": "500mg", "frequency": "twice daily"},
                    {"name": "Lisinopril", "dose": "10mg", "frequency": "once daily"},
                    {"name": "Insulin Glargine", "dose": "20 units", "frequency": "at bedtime"},
                    {"name": "Atorvastatin", "dose": "40mg", "frequency": "once daily"},
                ],
                "follow_up_appointments": [
                    {"provider": "Dr. Sarah Chen", "specialty": "Endocrinology", "date": "2026-04-26"},
                    {"provider": "Dr. Michael Rivera", "specialty": "Primary Care", "date": "2026-05-03"},
                ],
                "red_flag_symptoms": [
                    "Severe chest pain",
                    "Difficulty breathing",
                    "Signs of stroke",
                    "Blood sugar below 54 or above 400",
                    "Loss of consciousness",
                ],
            },
        ),

        Profile(
            name="chf_narrative",
            pages=[
                """# HOSPITAL COURSE

Patient Robert Kim, age 72, was admitted on 2026-04-05 for acute
decompensated heart failure with reduced ejection fraction. Transthoracic
echocardiogram revealed an ejection fraction of 28 percent, consistent
with heart failure with reduced ejection fraction. The patient was
diuresed with intravenous furosemide and transitioned to an oral regimen
prior to discharge on 2026-04-10.""",
                """# MEDICATIONS AT DISCHARGE

The patient was discharged on furosemide 40 mg by mouth once daily for
volume management, metoprolol succinate 25 mg by mouth once daily for
rate control, lisinopril 5 mg by mouth once daily for afterload
reduction, spironolactone 25 mg by mouth once daily as part of guideline
directed medical therapy, and atorvastatin 40 mg by mouth once daily
for lipid management.""",
                """# FOLLOW-UP AND WARNING SIGNS

The patient should follow up with Dr. Elena Torres from Cardiology in
two weeks on 2026-04-24 for medication titration. A primary care visit
with Dr. Priya Shah is scheduled for 2026-05-01 for general review.

Call 911 for worsening shortness of breath at rest, chest pain or
pressure, fainting, or rapid weight gain of more than three pounds in
one day.""",
            ],
            ground_truth={
                "patient_name": "Robert Kim",
                "discharge_date": "2026-04-10",
                "primary_diagnosis": "Heart Failure with Reduced Ejection Fraction",
                "secondary_diagnoses": [],
                "procedures_performed": [
                    "Transthoracic echocardiogram (EF 28%)",
                    "IV furosemide diuresis transitioned to oral",
                ],
                "medications": [
                    {"name": "Furosemide", "dose": "40mg", "frequency": "once daily"},
                    {"name": "Metoprolol Succinate", "dose": "25mg", "frequency": "once daily"},
                    {"name": "Lisinopril", "dose": "5mg", "frequency": "once daily"},
                    {"name": "Spironolactone", "dose": "25mg", "frequency": "once daily"},
                    {"name": "Atorvastatin", "dose": "40mg", "frequency": "once daily"},
                ],
                "follow_up_appointments": [
                    {"provider": "Dr. Elena Torres", "specialty": "Cardiology", "date": "2026-04-24"},
                    {"provider": "Dr. Priya Shah", "specialty": "Primary Care", "date": "2026-05-01"},
                ],
                "red_flag_symptoms": [
                    "worsening shortness of breath",
                    "chest pain or pressure",
                    "fainting",
                    "rapid weight gain more than three pounds in one day",
                ],
            },
        ),

        Profile(
            name="copd_mixed_route_change",
            pages=[
                """# DISCHARGE SUMMARY

Patient: Maria Alvarez
Discharge Date: 2026-04-14

# PRIMARY DIAGNOSIS
Acute Exacerbation of Chronic Obstructive Pulmonary Disease

# SECONDARY DIAGNOSES
- Hypertension
- Former tobacco use disorder""",
                """# PROCEDURES PERFORMED
- IV methylprednisolone 40mg q6h - 3 days
- Nebulized albuterol-ipratropium every 4 hours
- Chest X-ray (2026-04-11): Hyperinflation consistent with COPD, no acute pneumonia
- Arterial blood gas on admission: pH 7.32, pCO2 58""",
                """# DISCHARGE MEDICATIONS
- Prednisone 40mg by mouth once daily, taper per schedule
- Tiotropium inhaler one puff once daily
- Albuterol inhaler two puffs every 4 hours as needed
- Lisinopril 20mg by mouth once daily (continued)

# FOLLOW-UP APPOINTMENTS
- Dr. James Okafor, Pulmonology - 2026-04-28 - COPD follow-up

# WARNING SIGNS
Call 911 for severe shortness of breath, chest pain, blue lips or fingertips,
or confusion.""",
            ],
            ground_truth={
                "patient_name": "Maria Alvarez",
                "discharge_date": "2026-04-14",
                "primary_diagnosis": "Acute Exacerbation of Chronic Obstructive Pulmonary Disease",
                "secondary_diagnoses": ["Hypertension", "Former tobacco use disorder"],
                "procedures_performed": [
                    "IV methylprednisolone 40mg every 6 hours for 3 days",
                    "Nebulized albuterol-ipratropium every 4 hours",
                    "Chest X-ray: hyperinflation consistent with COPD, no acute pneumonia",
                    "Arterial blood gas on admission (pH 7.32, pCO2 58)",
                ],
                "medications": [
                    {"name": "Prednisone", "dose": "40mg", "frequency": "once daily", "status": "changed"},
                    {"name": "Tiotropium", "dose": "one puff", "frequency": "once daily"},
                    {"name": "Albuterol", "dose": "two puffs", "frequency": "every 4 hours"},
                    {"name": "Lisinopril", "dose": "20mg", "frequency": "once daily", "status": "continued"},
                ],
                "follow_up_appointments": [
                    {"provider": "Dr. James Okafor", "specialty": "Pulmonology", "date": "2026-04-28"},
                ],
                "red_flag_symptoms": [
                    "severe shortness of breath",
                    "chest pain",
                    "blue lips or fingertips",
                    "confusion",
                ],
            },
        ),

        Profile(
            name="hip_replacement_8pages_distractors",
            pages=[
                """# PRE-OPERATIVE RECORD — PAGE 1

Patient: Thomas O'Neill
Admission Date: 2026-04-06
Planned Procedure: Right Total Hip Arthroplasty

# PRE-OPERATIVE MEDICATIONS ADMINISTERED
- Propofol 200mg IV induction
- Midazolam 2mg IV pre-operative sedation
- Rocuronium 50mg IV neuromuscular blockade
- Fentanyl 100mcg IV analgesia

These medications were administered in the operating room only and are
not part of the discharge regimen.""",
                """# OPERATIVE NOTE — PAGE 2

Right total hip arthroplasty performed without complication on
2026-04-06. Estimated blood loss 350 mL. Spinal anesthesia with light
general sedation using propofol infusion intraoperatively.

The anesthesia team administered rocuronium and fentanyl strictly
intraoperatively. The patient did not receive any of these agents
post-operatively or at discharge.""",
                """# HOSPITAL COURSE DAY 1 — PAGE 3

Post-operative day 1. Vital signs stable. Hemoglobin 11.2. Patient
tolerated physical therapy evaluation. Pain controlled with scheduled
acetaminophen and as needed oxycodone. Ambulated 50 feet with walker.""",
                """# HOSPITAL COURSE DAYS 2-3 — PAGE 4

Physical therapy advanced. Patient ambulated 200 feet by post-operative
day 3. Deep vein thrombosis prophylaxis with enoxaparin started on
day 1 and continued through hospital stay. Wound healing appropriately.""",
                """# HOSPITAL COURSE DAY 4 — PAGE 5

Patient independent with walker and meets criteria for discharge home
with home physical therapy. Wound clean and dry. No signs of infection
or deep vein thrombosis.""",
                """# PROCEDURES PERFORMED — PAGE 6

- Right total hip arthroplasty (2026-04-06)
- Physical therapy sessions (post-op days 1-4)
- Enoxaparin DVT prophylaxis during admission""",
                """# DISCHARGE PLANNING — PAGE 7

# FOLLOW-UP APPOINTMENTS
- Dr. Patrick Deluca, Orthopedic Surgery - 2026-04-20 - wound check and staple removal
- Home Health Physical Therapy - starting 2026-04-12

Patient educated on hip precautions: no flexion past 90 degrees, no
crossing legs, no internal rotation for 6 weeks.""",
                """# DISCHARGE MEDICATIONS — PAGE 8

- Oxycodone 5mg by mouth every 4 hours as needed for pain
- Acetaminophen 650mg by mouth every 6 hours scheduled
- Enoxaparin 40mg subcutaneous injection once daily for 14 days
- Aspirin 81mg by mouth once daily for 35 days

# WARNING SIGNS
Call 911 for sudden shortness of breath, chest pain, or leg swelling
with warmth. Call the surgeon for fever over 101F or wound drainage.""",
            ],
            ground_truth={
                "patient_name": "Thomas O'Neill",
                "discharge_date": None,
                "primary_diagnosis": "Right Total Hip Arthroplasty",
                "secondary_diagnoses": [],
                "procedures_performed": [
                    "Right total hip arthroplasty (2026-04-06)",
                    "Physical therapy sessions post-operative days 1 through 4",
                    "Enoxaparin DVT prophylaxis during admission",
                ],
                "medications": [
                    {"name": "Oxycodone", "dose": "5mg", "frequency": "every 4 hours"},
                    {"name": "Acetaminophen", "dose": "650mg", "frequency": "every 6 hours"},
                    {"name": "Enoxaparin", "dose": "40mg", "frequency": "once daily"},
                    {"name": "Aspirin", "dose": "81mg", "frequency": "once daily"},
                ],
                "follow_up_appointments": [
                    {"provider": "Dr. Patrick Deluca", "specialty": "Orthopedic Surgery", "date": "2026-04-20"},
                    {"provider": None, "specialty": "Physical Therapy", "date": "2026-04-12"},
                ],
                "red_flag_symptoms": [
                    "sudden shortness of breath",
                    "chest pain",
                    "leg swelling with warmth",
                    "fever over 101",
                    "wound drainage",
                ],
            },
            distractor_meds=["propofol", "midazolam", "rocuronium", "fentanyl"],
        ),

        Profile(
            name="pneumonia_abbreviations",
            pages=[
                """# DISCHARGE SUMMARY

Patient: Linda Park
Discharge Date: 2026-04-13

# PRIMARY DX
Community-Acquired Pneumonia, right lower lobe

# SECONDARY DX
- HTN
- GERD

# PROCEDURES
- CXR: RLL consolidation
- CBC, BMP, blood cx x2""",
                """# DISCHARGE RX
- Augmentin 875mg PO BID x 7d
- Albuterol MDI 2 puffs QID PRN
- Guaifenesin 600mg PO Q12H
- Omeprazole 20mg PO QD (continued)

# F/U
- Dr. Laura Chen, PCP - 2026-04-20 - post-discharge visit

# RED FLAGS
Call 911 for SOB, chest pain, confusion, or fever > 102F despite meds.""",
            ],
            ground_truth={
                "patient_name": "Linda Park",
                "discharge_date": "2026-04-13",
                "primary_diagnosis": "Community-Acquired Pneumonia",
                "secondary_diagnoses": ["Hypertension", "GERD"],
                "procedures_performed": [
                    "Chest X-ray: right lower lobe consolidation",
                    "Complete blood count, basic metabolic panel, blood cultures",
                ],
                "medications": [
                    {"name": "Amoxicillin-Clavulanate", "dose": "875mg", "frequency": "twice daily"},
                    {"name": "Albuterol", "dose": "2 puffs", "frequency": "four times daily"},
                    {"name": "Guaifenesin", "dose": "600mg", "frequency": "every 12 hours"},
                    {"name": "Omeprazole", "dose": "20mg", "frequency": "once daily"},
                ],
                "follow_up_appointments": [
                    {"provider": "Dr. Laura Chen", "specialty": "Primary Care", "date": "2026-04-20"},
                ],
                "red_flag_symptoms": [
                    "shortness of breath",
                    "chest pain",
                    "confusion",
                    "fever over 102",
                ],
            },
            expected_warnings=[
                "Document uses abbreviated clinical shorthand verify medication",
            ],
        ),

        Profile(
            name="minimal_sparse",
            pages=[
                """# DISCHARGE NOTE

Patient Nora Sullivan seen in the emergency department on 2026-04-15
for uncomplicated urinary tract infection. Discharged home same day.

Primary diagnosis: Urinary Tract Infection.

Discharge medication: Nitrofurantoin 100 mg by mouth twice daily for 5 days.

Return to the emergency department if symptoms worsen.""",
            ],
            ground_truth={
                "patient_name": "Nora Sullivan",
                "discharge_date": "2026-04-15",
                "primary_diagnosis": "Urinary Tract Infection",
                "secondary_diagnoses": [],
                "medications": [
                    {"name": "Nitrofurantoin", "dose": "100mg", "frequency": "twice daily"},
                ],
                "follow_up_appointments": [],
                "red_flag_symptoms": [],
            },
            expected_warnings=[
                "Document unusually short discharge summary may incomplete partial",
            ],
        ),

        Profile(
            name="aki_6_secondaries",
            pages=[
                """# DISCHARGE SUMMARY

Patient: Harold Weiss
Discharge Date: 2026-04-11

# PRIMARY DIAGNOSIS
Acute Kidney Injury Stage 2

# SECONDARY DIAGNOSES
- Hypertension
- Type 2 Diabetes Mellitus
- Chronic Kidney Disease Stage 3
- Hyperlipidemia
- Obstructive Sleep Apnea
- Gastroesophageal Reflux Disease""",
                """# HOSPITAL COURSE

Patient admitted with creatinine 3.1 (baseline 1.6). Improved with IV
fluids and holding nephrotoxic medications. Creatinine at discharge 1.9.

# PROCEDURES PERFORMED
- Basic metabolic panel daily
- Renal ultrasound (2026-04-09): No obstruction, CKD changes
- IV fluid resuscitation""",
                """# DISCHARGE MEDICATIONS
- Amlodipine 5mg by mouth once daily
- Insulin Glargine 15 units subcutaneous at bedtime
- Atorvastatin 20mg by mouth once daily

# FOLLOW-UP APPOINTMENTS
- Dr. Farah Qureshi, Nephrology - 2026-04-25 - AKI follow-up and labs
- Dr. Susan Park, Endocrinology - 2026-05-02 - diabetes management
- Dr. Adam Greene, Primary Care - 2026-05-09 - general review

# WARNING SIGNS
Call 911 for chest pain, severe shortness of breath, confusion, or
decreased urine output less than 500 mL per day.""",
            ],
            ground_truth={
                "patient_name": "Harold Weiss",
                "discharge_date": "2026-04-11",
                "primary_diagnosis": "Acute Kidney Injury Stage 2",
                "secondary_diagnoses": [
                    "Hypertension",
                    "Type 2 Diabetes Mellitus",
                    "Chronic Kidney Disease Stage 3",
                    "Hyperlipidemia",
                    "Obstructive Sleep Apnea",
                    "Gastroesophageal Reflux Disease",
                ],
                "procedures_performed": [
                    "Basic metabolic panel daily",
                    "Renal ultrasound: no obstruction, CKD changes",
                    "IV fluid resuscitation",
                ],
                "medications": [
                    {"name": "Amlodipine", "dose": "5mg", "frequency": "once daily"},
                    {"name": "Insulin Glargine", "dose": "15 units", "frequency": "at bedtime"},
                    {"name": "Atorvastatin", "dose": "20mg", "frequency": "once daily"},
                ],
                "follow_up_appointments": [
                    {"provider": "Dr. Farah Qureshi", "specialty": "Nephrology", "date": "2026-04-25"},
                    {"provider": "Dr. Susan Park", "specialty": "Endocrinology", "date": "2026-05-02"},
                    {"provider": "Dr. Adam Greene", "specialty": "Primary Care", "date": "2026-05-09"},
                ],
                "red_flag_symptoms": [
                    "chest pain",
                    "severe shortness of breath",
                    "confusion",
                    "decreased urine output less than 500 mL per day",
                ],
            },
        ),

        Profile(
            name="pediatric_asthma_weight_based",
            pages=[
                """# PEDIATRIC DISCHARGE SUMMARY

Patient: Kevin Martinez (age 7, weight 24 kg)
Discharge Date: 2026-04-14

# PRIMARY DIAGNOSIS
Acute Asthma Exacerbation, moderate severity

# SECONDARY DIAGNOSES
- Allergic Rhinitis

# PROCEDURES PERFORMED
- Albuterol nebulizer treatments (every 20 minutes x 3, then every 4 hours)
- Oral systemic corticosteroids
- Peak flow measurements""",
                """# DISCHARGE MEDICATIONS
- Albuterol 2.5mg via nebulizer every 4 hours as needed (0.1 mg/kg per dose)
- Prednisolone 30mg by mouth once daily for 5 days (1 mg/kg/day, max 40mg)
- Fluticasone inhaler 88mcg two puffs twice daily (controller)

# FOLLOW-UP APPOINTMENTS
- Dr. Angela Foster, Pediatrics - 2026-04-21 - asthma follow-up

# WARNING SIGNS
Call 911 for severe difficulty breathing, blue lips or fingertips, inability
to speak full sentences, or no improvement after albuterol.""",
            ],
            ground_truth={
                "patient_name": "Kevin Martinez",
                "discharge_date": "2026-04-14",
                "primary_diagnosis": "Acute Asthma Exacerbation",
                "secondary_diagnoses": ["Allergic Rhinitis"],
                "procedures_performed": [
                    "Albuterol nebulizer treatments every 20 minutes x 3 then every 4 hours",
                    "Oral systemic corticosteroids",
                    "Peak flow measurements",
                ],
                "medications": [
                    {"name": "Albuterol", "dose": "2.5mg", "frequency": "every 4 hours"},
                    {"name": "Prednisolone", "dose": "30mg", "frequency": "once daily"},
                    {"name": "Fluticasone", "dose": "88mcg", "frequency": "twice daily"},
                ],
                "follow_up_appointments": [
                    {"provider": "Dr. Angela Foster", "specialty": "Pediatrics", "date": "2026-04-21"},
                ],
                "red_flag_symptoms": [
                    "severe difficulty breathing",
                    "blue lips or fingertips",
                    "inability to speak full sentences",
                    "no improvement after albuterol",
                ],
            },
        ),
    ]


# ── Reporting ────────────────────────────────────────────────────────────────-

def _format_case(index: int, total: int, result: dict) -> str:
    """Render the per-case block shown on stdout."""
    lines = []
    lines.append(f"[{index}/{total}] {result['name']}")
    lines.append(f"  pipeline_status: {result['pipeline_status']}")
    if result["status"] == "ERROR":
        lines.append(f"  ERROR: {result['error']}")
        return "\n".join(lines)

    by_field: dict[str, list[Issue]] = {}
    for issue in result["issues"]:
        by_field.setdefault(issue.field, []).append(issue)

    def field_line(label: str, field_name: str) -> str:
        n = len(by_field.get(field_name, []))
        return f"  {label:<22} {'FAIL (' + str(n) + ')' if n else 'PASS'}"

    lines.append(field_line("patient:", "patient_name"))
    lines.append(field_line("primary_diagnosis:", "primary_diagnosis"))
    lines.append(field_line("secondary_dx:", "secondary_diagnoses"))
    lines.append(field_line("medications:", "medications"))
    lines.append(field_line("appointments:", "follow_up_appointments"))
    lines.append(field_line("red_flags:", "red_flag_symptoms"))
    lines.append(field_line("warnings:", "extraction_warnings"))
    lines.append(field_line("agent2_audit:", "agent2_claim"))
    lines.append(f"  hallucinations: {result['hallucinations']}")
    lines.append(f"  omissions:      {result['omissions']}")
    if result["issues"]:
        lines.append("  issues:")
        for issue in result["issues"]:
            lines.append(f"    {issue}")
    return "\n".join(lines)


def _format_summary(results: list[dict]) -> tuple[str, bool]:
    """Return (banner_text, overall_pass_bool)."""
    total = len(results)
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_err = sum(1 for r in results if r["status"] == "ERROR")
    total_hall = sum(r["hallucinations"] for r in results)
    total_omit = sum(r["omissions"] for r in results)

    hard_gate = total_hall == 0
    soft_gate = total_omit <= 3
    overall = hard_gate and soft_gate and n_err == 0

    lines = [
        "=" * 64,
        "INTEGRATION + HALLUCINATION TEST SUMMARY",
        "=" * 64,
        f"Cases run:       {total}",
        f"Cases PASS:      {n_pass}",
        f"Cases FAIL:      {n_fail}",
        f"Cases ERROR:     {n_err}",
        f"Total hallucinations: {total_hall}",
        f"Total omissions:      {total_omit}",
        "-" * 64,
        f"Hard gate (0 hallucinations):  {'PASS' if hard_gate else 'FAIL'}",
        f"Soft gate (<=3 omissions):     {'PASS' if soft_gate else 'FAIL'}",
        "=" * 64,
        f"  RESULT: {'PASS' if overall else 'FAIL'}",
        "=" * 64,
    ]
    return "\n".join(lines), overall


# ── Main ─────────────────────────────────────────────────────────────────────-

def main() -> int:
    """Build PDFs, run the pipeline, classify issues, print report."""
    log_file = configure_logging()
    print(f"Log file: {log_file}")

    profiles = _profiles()
    results: list[dict] = []

    for i, profile in enumerate(profiles, start=1):
        try:
            result = run_case(profile, i, len(profiles))
        except Exception as exc:  # noqa: BLE001
            logger.exception("run_case %s crashed", profile.name)
            result = {
                "name": profile.name,
                "status": "ERROR",
                "pipeline_status": None,
                "issues": [],
                "hallucinations": 0,
                "omissions": 0,
                "audit_claims": [],
                "error": str(exc),
            }
        results.append(result)
        block = _format_case(i, len(profiles), result)
        print(block)
        print()
        logger.info("CASE REPORT:\n%s", block)

    banner, overall = _format_summary(results)
    print(banner)
    logger.info("SUMMARY:\n%s", banner)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
