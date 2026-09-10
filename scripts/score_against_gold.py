#!/usr/bin/env python3
"""
scripts/score_against_gold.py

Score Agent 1's extraction against clinician annotations, and report
entity-level precision and recall with confidence intervals.
Owner: Likitha Shankar.

Closes the scoring half of Liebovitz item 3.4. The annotation schema is
docs/ANNOTATION_SCHEMA.md; this is the tool it promises.

WHAT THIS MEASURES THAT NOTHING ELSE DOES
-----------------------------------------
Every accuracy figure the project reports today measures extraction to
patient-facing output, with the extraction as its own reference. That leg is
real and it is not the whole risk: a medication Agent 1 never saw cannot show
up as a miss, so the published recall is an UPPER BOUND. The source-to-
extraction leg needs a human who read the document, and this scores against
what that human wrote down.

Errors of omission are the target, because they are invisible downstream: a
dropped medication yields a clean, confident, incorrect document.

WHY MATCHING IS THE HARD PART
-----------------------------
Naive string equality would report "Lasix 40mg" against "furosemide 40 mg" as
one miss AND one fabrication - two errors where there is none, in the
direction that makes the system look worse than it is. So names are
normalised, a brand/generic map is applied, and anything still unmatched is
reported for a human to adjudicate rather than silently scored either way.

The categories are deliberately four, not two:

  matched            the entity is in both
  system_miss        in the annotation, not in the extraction  <- the number
                     that matters
  system_extra       in the extraction, not in the annotation. NOT the same as
                     a fabrication: the annotator may have missed it. Only a
                     human can tell those apart, so this tool never calls it
                     one.
  dose_mismatch      same drug, different dose. Counted separately because a
                     silently wrong dose is not a recall failure and is
                     arguably worse than a missing one.

Usage:
  python scripts/score_against_gold.py
  python scripts/score_against_gold.py --doc mtsamples_014 --verbose
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ANNOTATIONS = _REPO / "evaluation" / "annotations"
_OUTPUTS = _REPO / "evaluation" / "corpus_outputs"

#: Brand and generic names that must not score as two different drugs.
#:
#: Deliberately short and boring. This is clinical content in a scoring tool,
#: so it holds only pairs that are unambiguous and widely known, and it is NOT
#: exhaustive - an unlisted pair falls through to the adjudication list, which
#: is the safe direction. A clinician should extend it; nobody should assume
#: it is complete.
_BRAND_GENERIC = {
    "lasix": "furosemide",
    "coumadin": "warfarin",
    "glucophage": "metformin",
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "coreg": "carvedilol",
    "lopressor": "metoprolol",
    "toprol": "metoprolol",
    "norvasc": "amlodipine",
    "zocor": "simvastatin",
    "lipitor": "atorvastatin",
    "plavix": "clopidogrel",
    "protonix": "pantoprazole",
    "ventolin": "albuterol",
    "proventil": "albuterol",
    "spiriva": "tiotropium",
    "advair": "fluticasone-salmeterol",
    "eliquis": "apixaban",
    "xarelto": "rivaroxaban",
    "synthroid": "levothyroxine",
}

#: Dose-form and route words that carry no identity. "Furosemide tablet" and
#: "furosemide" are the same drug.
_NOISE = re.compile(
    r"\b(tab(let)?s?|cap(sule)?s?|po|oral(ly)?|iv|im|sub ?q|inhaler|"
    r"solution|suspension|er|xr|sr|cr|dpi|mdi)\b",
    re.IGNORECASE,
)


def normalise_drug(name: str) -> str:
    """
    Reduce a drug name to something comparable.

    Lowercases, drops punctuation, strips dose-form and route words, and maps
    a known brand to its generic. Combination products keep both parts, joined
    by a hyphen, so "fluticasone/salmeterol" and "fluticasone-salmeterol"
    agree.

    Args:
        name: Raw name from either side.

    Returns:
        str: Normalised key, or "" when nothing identifying is left.
    """
    text = (name or "").lower().strip()
    # A parenthetical alias is the same drug named twice, not a compound.
    # Discharge documents routinely write "Warfarin (Coumadin) 5 mg", and
    # stripping only the punctuation leaves "warfarin coumadin", which matches
    # neither "warfarin" nor "coumadin" - so the drug reads as missing from
    # the extraction AND invented by it, which is the two-errors-where-there-
    # is-none failure this function exists to prevent.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[/+]", "-", text)
    text = re.sub(r"[^\w\s-]", " ", text)
    text = _NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Only the leading token carries identity; trailing strength or form does
    # not. "furosemide 40 mg" and "furosemide" must agree, because dose is
    # compared separately and a dose difference is its own category.
    text = re.sub(r"\s*\d.*$", "", text).strip()
    parts = [_BRAND_GENERIC.get(p, p) for p in text.split("-") if p]
    return "-".join(parts)


def normalise_dose(dose: str | None) -> str:
    """
    Comparable form of a dose string.

    "40mg", "40 mg" and "40 MG" are the same dose. A missing dose normalises
    to "", which never counts as a mismatch - a document that gave no dose is
    not a disagreement about the dose.
    """
    text = (dose or "").lower()
    text = re.sub(r"[^\w.]", "", text)
    return text


def normalise_text(text: str) -> str:
    """Loose comparable form for free-text entities like warning signs."""
    cleaned = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """
    Wilson score interval, as percentages.

    Used rather than the normal approximation because the counts here are
    small and the proportions are near 1, exactly where the normal interval
    misbehaves and can run past 100%.

    Returns:
        tuple[float, float]: (low, high) as percentages. (0, 100) when total
        is zero, which is honest about knowing nothing.
    """
    if total <= 0:
        return (0.0, 100.0)
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z / denominator * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total))
    return (max(0.0, (centre - margin) * 100), min(100.0, (centre + margin) * 100))


def score_medications(gold: list, extracted: list) -> dict:
    """
    Match annotated medications against extracted ones.

    Returns:
        dict: matched / system_miss / system_extra / dose_mismatch, each a
        list of human-readable descriptions, plus the counts behind them.
    """
    gold_by_key: dict[str, list] = {}
    for entry in gold:
        if not isinstance(entry, dict):
            continue
        key = normalise_drug(entry.get("name", ""))
        if key:
            gold_by_key.setdefault(key, []).append(entry)

    extracted_by_key: dict[str, list] = {}
    for entry in extracted:
        if not isinstance(entry, dict):
            continue
        key = normalise_drug(entry.get("name", ""))
        if key:
            extracted_by_key.setdefault(key, []).append(entry)

    matched, dose_mismatch = [], []
    system_miss, system_extra = [], []

    for key, gold_entries in gold_by_key.items():
        found_entries = extracted_by_key.get(key, [])
        for gold_entry, found_entry in zip(gold_entries, found_entries):
            gold_dose = normalise_dose(gold_entry.get("dose"))
            found_dose = normalise_dose(found_entry.get("dose"))
            # An absent dose on either side is not a disagreement. Only two
            # stated doses that differ are.
            if gold_dose and found_dose and gold_dose != found_dose:
                dose_mismatch.append(
                    f"{key}: annotated {gold_entry.get('dose')!r}, "
                    f"extracted {found_entry.get('dose')!r}")
            else:
                matched.append(key)
        # Leftovers on either side of the zip.
        #
        # A drug can legitimately appear twice - metoprolol 25 mg in the
        # morning and 50 mg at night - so the counts under one key need not
        # agree. zip() alone dropped the surplus silently: the second entry
        # was neither matched nor missed, it simply vanished from the
        # arithmetic. An entity disappearing without trace is the exact
        # failure this tool exists to detect, so it must not happen inside
        # the tool. Caught by checking that every gold entry is accounted
        # for, which is now asserted in the tests.
        for surplus in gold_entries[len(found_entries):]:
            system_miss.append(f"{key} ({surplus.get('dose') or 'no dose'})")
        for surplus in found_entries[len(gold_entries):]:
            system_extra.append(f"{key} ({surplus.get('dose') or 'no dose'})")

    for key, found_entries in extracted_by_key.items():
        if key not in gold_by_key:
            system_extra.extend(
                f"{key} ({e.get('dose') or 'no dose'})" for e in found_entries)

    return {
        "matched": matched,
        "system_miss": system_miss,
        "system_extra": system_extra,
        "dose_mismatch": dose_mismatch,
    }


def score_appointments(gold: list, extracted: list) -> dict:
    """
    Match annotated appointments against extracted ones.

    Keyed on specialty-or-provider plus the date AS WRITTEN. Relative dates
    ("in 2 weeks") are compared verbatim on purpose: the schema forbids the
    annotator resolving them, because Agent 1 is forbidden to, and resolving
    on one side only would score correct behaviour as wrong.
    """
    def key_of(entry: dict) -> str:
        who = normalise_text(entry.get("specialty") or entry.get("provider") or "")
        when = normalise_text(str(entry.get("date") or ""))
        return f"{who}|{when}"

    gold_keys = {key_of(e) for e in gold if isinstance(e, dict)}
    found_keys = {key_of(e) for e in extracted if isinstance(e, dict)}
    gold_keys.discard("|")
    found_keys.discard("|")
    return {
        "matched": sorted(gold_keys & found_keys),
        "system_miss": sorted(gold_keys - found_keys),
        "system_extra": sorted(found_keys - gold_keys),
        "dose_mismatch": [],
    }


def score_warnings(gold: list, extracted: list) -> dict:
    """
    Match annotated warning signs against extracted ones.

    Free text, so exact matching would be meaningless. A gold sign counts as
    found when it shares a distinctive content word with an extracted one -
    "swelling in the legs" matches "leg swelling". Loose on purpose: the risk
    worth catching is a warning sign that vanished entirely, and a strict
    matcher would drown that signal in wording differences.

    The looseness is stated rather than hidden. This number is a floor on
    omission, and near-misses land in the adjudication list.
    """
    stop = {"the", "a", "an", "of", "or", "and", "in", "your", "you", "if",
            "is", "are", "to", "for", "with", "that", "this", "any", "more",
            "than", "over", "call", "doctor", "have", "has", "get", "new"}

    def tokens(text: str) -> set[str]:
        return {w for w in normalise_text(text).split() if w not in stop and len(w) > 3}

    gold_items = [(g.get("text", "") if isinstance(g, dict) else str(g)) for g in gold]
    found_tokens = [tokens(str(f)) for f in extracted]

    matched, missed = [], []
    for item in gold_items:
        item_tokens = tokens(item)
        if item_tokens and any(item_tokens & ft for ft in found_tokens):
            matched.append(item)
        else:
            missed.append(item)
    return {
        "matched": matched,
        "system_miss": missed,
        "system_extra": [],
        "dose_mismatch": [],
    }


def score_document(annotation: dict, output: dict) -> dict:
    """Score one annotated document against its pipeline output."""
    extraction = output.get("extraction") or {}
    return {
        "medications": score_medications(
            annotation.get("medications") or [],
            extraction.get("medications") or []),
        "appointments": score_appointments(
            annotation.get("follow_up_appointments") or [],
            extraction.get("follow_up_appointments") or []),
        "warning_signs": score_warnings(
            annotation.get("warning_signs") or [],
            extraction.get("red_flag_symptoms") or []),
    }


def _totals(per_document: list[tuple[str, dict]], category: str) -> dict:
    """Aggregate one category across documents."""
    matched = miss = extra = dose = 0
    for _, scores in per_document:
        block = scores[category]
        matched += len(block["matched"])
        miss += len(block["system_miss"])
        extra += len(block["system_extra"])
        dose += len(block["dose_mismatch"])
    in_gold = matched + miss + dose
    in_system = matched + extra + dose
    return {
        "matched": matched, "miss": miss, "extra": extra, "dose": dose,
        "recall": (matched / in_gold * 100) if in_gold else None,
        "recall_ci": wilson(matched, in_gold),
        "precision": (matched / in_system * 100) if in_system else None,
        "precision_ci": wilson(matched, in_system),
        "in_gold": in_gold, "in_system": in_system,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", help="score one document only")
    parser.add_argument("--verbose", action="store_true",
                        help="list every disagreement for adjudication")
    args = parser.parse_args()

    print("=" * 68)
    print("DischargeIQ - extraction against clinician gold standard")
    print("=" * 68)

    if not _ANNOTATIONS.exists() or not any(_ANNOTATIONS.glob("*.json")):
        print(f"\nNo annotations in {_ANNOTATIONS.relative_to(_REPO)}/.")
        print("This is the expected state until a clinician has annotated "
              "documents.\nThe format is docs/ANNOTATION_SCHEMA.md; drop one "
              "JSON file per document\ninto that directory and re-run.")
        return 0

    per_document = []
    for path in sorted(_ANNOTATIONS.glob("*.json")):
        if args.doc and path.stem != args.doc:
            continue
        try:
            annotation = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as err:
            print(f"  SKIP {path.stem}: unreadable ({err})")
            continue
        output_path = _OUTPUTS / f"{path.stem}.json"
        if not output_path.exists():
            print(f"  SKIP {path.stem}: no pipeline output to compare against")
            continue
        output = json.loads(output_path.read_text())
        per_document.append((path.stem, score_document(annotation, output)))

    if not per_document:
        print("\nNothing to score.")
        return 0

    print(f"\nscored {len(per_document)} document(s)\n")
    for category in ("medications", "appointments", "warning_signs"):
        totals = _totals(per_document, category)
        print(f"  {category}")
        if totals["in_gold"]:
            low, high = totals["recall_ci"]
            print(f"    recall     {totals['recall']:5.1f}%   "
                  f"({totals['matched']}/{totals['in_gold']})   "
                  f"95% CI {low:.1f}-{high:.1f}")
        if totals["in_system"]:
            low, high = totals["precision_ci"]
            print(f"    precision  {totals['precision']:5.1f}%   "
                  f"({totals['matched']}/{totals['in_system']})   "
                  f"95% CI {low:.1f}-{high:.1f}")
        if totals["dose"]:
            print(f"    dose mismatches  {totals['dose']}")
        print()

    # The adjudication list. Never scored automatically: only a human can say
    # whether an extra entity is a fabrication or something the annotator
    # missed, and guessing would put a number on a judgement nobody made.
    print("-" * 68)
    print("FOR ADJUDICATION - a human decides each of these")
    print("-" * 68)
    any_disagreement = False
    for doc_id, scores in per_document:
        lines = []
        for category, block in scores.items():
            for item in block["system_miss"]:
                lines.append(f"    system_miss     [{category}] {item}")
            for item in block["system_extra"]:
                lines.append(f"    needs_review    [{category}] {item} "
                             f"(fabrication, or the annotator missed it?)")
            for item in block["dose_mismatch"]:
                lines.append(f"    dose_mismatch   [{category}] {item}")
        if lines:
            any_disagreement = True
            print(f"\n  {doc_id}")
            for line in (lines if args.verbose else lines[:6]):
                print(line)
            if not args.verbose and len(lines) > 6:
                print(f"    ... {len(lines) - 6} more (--verbose)")
    if not any_disagreement:
        print("\n  none - extraction and annotation agree everywhere")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
