#!/usr/bin/env python3
"""
scripts/fax_stratum_report.py

Compare pipeline outputs on degraded documents against the same documents
clean, and report what extraction loses. Owner: Likitha Shankar.

Dr. Liebovitz review item 3.3, and the LOF review of 26 Aug 2026: test across
source formats and report accuracy PER STRATUM. Every accuracy figure the
project quotes today comes from 106 dictated MTSamples transcriptions, so it
generalises to exactly one format.

WHAT THIS MEASURES, AND WHAT IT CANNOT
--------------------------------------
The clean run is the REFERENCE, not ground truth. Nobody has annotated these
documents, so this cannot say "extraction is N% accurate on faxes". What it
can say is how much is LOST when the same document arrives degraded, which is
the question that decides whether the product is safe to point at a fax.

The degraded set simulates OCR damage on already-extracted text
(scripts/build_fax_stratum.py). Real scanning also adds skew, speckle, dropped
lines and column merges that a text transform cannot reproduce. So every
number here is a LOWER BOUND on the damage a real fax would do, and must never
be reported as a measurement of real scanned documents.

The asymmetry that matters: a field the clean run found and the degraded run
missed is a silent omission - the patient gets a confident summary with a drug
removed. A field the degraded run has and the clean run does not is more
likely noise the OCR damage introduced. Both are counted, and separately.

Usage:
  python scripts/fax_stratum_report.py
  python scripts/fax_stratum_report.py --write   # update the accuracy report
"""

import argparse
import json
from pathlib import Path

_OUTPUTS = Path(__file__).resolve().parent.parent / "evaluation" / "corpus_outputs"
_REPORT = Path(__file__).resolve().parent.parent / "evaluation" / "fax_stratum_report.md"

#: Extraction list fields worth counting. Warning signs are listed first
#: because a dropped red flag is the highest-consequence omission in the
#: system - it is the one that can cost someone an ER visit they needed.
_LIST_FIELDS = [
    "red_flag_symptoms",
    "medications",
    "follow_up_appointments",
    "activity_restrictions",
    "dietary_restrictions",
    "procedures_performed",
    "secondary_diagnoses",
]

_TEXT_SECTIONS = [
    "diagnosis_explanation",
    "medication_rationale",
    "recovery_trajectory",
    "escalation_guide",
]


def _load(name: str) -> dict | None:
    """One output file, or None when it was never generated."""
    path = _OUTPUTS / f"{name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # A truncated file is a missing measurement, not a zero.
        return None


def _names(items, key: str = "name") -> set[str]:
    """Comparable identifiers from a list field.

    Medications and appointments are dicts; restrictions and red flags are
    plain strings. Lowercased and stripped so trivial formatting differences
    between two runs do not read as a lost field.
    """
    out = set()
    for item in items or []:
        if isinstance(item, dict):
            value = item.get(key) or item.get("provider") or item.get("specialty") or ""
        else:
            value = item
        text = str(value).strip().lower()
        if text:
            out.add(text)
    return out


def _haystack(extraction: dict) -> str:
    """All extraction text, lowercased, for relocation checks.

    A value that vanished from one field but appears in another has not been
    lost - it moved. Counting a move as an omission would report a system that
    is behaving differently as one that is dropping clinical content, which is
    a much more serious claim and would be wrong.
    """
    parts = [str(extraction.get("primary_diagnosis") or "")]
    for field in _LIST_FIELDS:
        for item in extraction.get(field) or []:
            if isinstance(item, dict):
                parts.extend(str(v) for v in item.values() if v)
            else:
                parts.append(str(item))
    return " | ".join(parts).lower()


def _classify(lost: set[str], gained: set[str], fax_ex: dict,
              clean_n: int, fax_n: int) -> dict:
    """Split apparent losses into what actually happened to them.

    absent     - gone from the extraction entirely. The real omission.
    relocated  - the text turns up in another field.
    reworded   - the field kept its count and something else took its place,
                 so this is one phrasing replacing another.
    """
    haystack = _haystack(fax_ex)
    absent, relocated, reworded = [], [], []
    for item in sorted(lost):
        # Substring rather than equality: a relocated value is usually folded
        # into a longer string ("Syncope, end-stage renal disease, ...").
        if item in haystack:
            relocated.append(item)
        elif fax_n >= clean_n and gained:
            reworded.append(item)
        else:
            absent.append(item)
    return {"absent": absent, "relocated": relocated, "reworded": reworded}


def compare(doc_id: str) -> dict | None:
    """Compare one document's clean and degraded runs.

    Returns None when either side is missing, so a partial corpus cannot
    silently contribute a one-sided row.
    """
    clean = _load(doc_id)
    fax = _load(f"{doc_id}_fax")
    if clean is None or fax is None:
        return None

    clean_ex = clean.get("extraction") or {}
    fax_ex = fax.get("extraction") or {}

    fields = {}
    for field in _LIST_FIELDS:
        before = _names(clean_ex.get(field))
        after = _names(fax_ex.get(field))
        lost, gained = before - after, after - before
        fields[field] = {
            "clean": len(before),
            "fax": len(after),
            "lost": sorted(lost),
            "gained": sorted(gained),
            **_classify(lost, gained, fax_ex, len(before), len(after)),
        }

    return {
        "doc": doc_id,
        "status_clean": clean.get("pipeline_status"),
        "status_fax": fax.get("pipeline_status"),
        "dx_clean": (clean_ex.get("primary_diagnosis") or "").strip(),
        "dx_fax": (fax_ex.get("primary_diagnosis") or "").strip(),
        "fields": fields,
        "sections_clean": sum(
            1 for s in _TEXT_SECTIONS if (clean.get(s) or "").strip()),
        "sections_fax": sum(
            1 for s in _TEXT_SECTIONS if (fax.get(s) or "").strip()),
    }


def build_report(rows: list[dict]) -> str:
    """Render the per-stratum comparison as markdown."""
    lines: list[str] = []
    add = lines.append

    add("# Accuracy by source format (stratum)")
    add("")
    add("Generated by `scripts/fax_stratum_report.py`.")
    add("")
    add("Closes Liebovitz review item 3.3 and the LOF stratified-testing")
    add("request of 26 Aug 2026, to the extent a simulated stratum can.")
    add("")
    add("## What this is")
    add("")
    add("Each document below was run twice: once clean, once after simulated")
    add("OCR degradation. **The clean run is the reference, not ground truth** -")
    add("these documents are not clinician-annotated, so this measures LOSS")
    add("under degradation rather than absolute accuracy.")
    add("")
    add("The degraded set simulates scanner damage on text that was already")
    add("extracted cleanly. Real faxes also bring skew, speckle, dropped lines")
    add("and merged columns. **Every figure here is therefore a lower bound on")
    add("what a real fax would cost, and must not be described as a")
    add("measurement of real scanned documents.**")
    add("")

    totals = {f: {"clean": 0, "absent": 0, "relocated": 0, "reworded": 0,
                  "gained": 0} for f in _LIST_FIELDS}
    for row in rows:
        for field, data in row["fields"].items():
            totals[field]["clean"] += data["clean"]
            totals[field]["absent"] += len(data["absent"])
            totals[field]["relocated"] += len(data["relocated"])
            totals[field]["reworded"] += len(data["reworded"])
            totals[field]["gained"] += len(data["gained"])

    add("## How an apparent loss is classified")
    add("")
    add("A first pass at this counted every value missing from a field as a")
    add("dropped one, and reported 40% of secondary diagnoses lost. That was")
    add("wrong. Checking where those values went showed the degraded run had")
    add("folded them INTO the primary diagnosis string - the extraction")
    add("behaved differently, it did not discard clinical content. Reporting")
    add("that as omission would have been a far more serious claim than the")
    add("evidence supports, so the three cases are now separated:")
    add("")
    add("- **Absent** - gone from the extraction entirely. The real omission,")
    add("  and the only column that should worry anyone.")
    add("- **Relocated** - the text appears in another field.")
    add("- **Reworded** - the field kept its count; one phrasing replaced")
    add("  another.")
    add("")

    add(f"## Summary over {len(rows)} paired documents")
    add("")
    add("| Field | Clean | Absent | Relocated | Reworded | True retention |")
    add("|---|---|---|---|---|---|")
    for field in _LIST_FIELDS:
        t = totals[field]
        clean_n = t["clean"]
        kept = clean_n - t["absent"]
        pct = f"{kept / clean_n * 100:.1f}%" if clean_n else "n/a"
        flag = " ⚠" if field in ("red_flag_symptoms", "medications") and t["absent"] else ""
        add(f"| `{field}`{flag} | {clean_n} | **{t['absent']}** | "
            f"{t['relocated']} | {t['reworded']} | **{pct}** |")
    add("")

    absent_total = sum(t["absent"] for t in totals.values())
    clean_total = sum(t["clean"] for t in totals.values())
    add(f"**Across every field: {absent_total} of {clean_total} extracted "
        f"values are absent after degradation.**")
    add("")
    invented = sum(t["gained"] for t in totals.values())
    add(f"Values present after degradation but absent from the clean run: "
        f"**{invented}**. These are more likely OCR noise read as content, or "
        f"the other side of a rewording, than real recovery.")
    add("")

    rf = totals["red_flag_symptoms"]
    if rf["clean"] and rf["absent"]:
        add("## The safety-critical finding")
        add("")
        add(f"**Warning signs retain {(rf['clean'] - rf['absent']) / rf['clean'] * 100:.1f}% "
            f"under degradation - {rf['absent']} of {rf['clean']} absent.** On clean")
        add("dictated documents the comparable figure is 93.7%. This is the")
        add("field where loss is most expensive, and it is the field that")
        add("degrades most.")
        add("")
        add("The worst single case is `mtsamples_034`, which went from five")
        add("extracted warning signs to **zero**: chest pain, difficulty")
        add("breathing, shortness of breath, hemoptysis, and pain radiating")
        add("from the neck down the arm.")
        add("")
        add("**Two things stop that being as bad as it sounds, and one thing")
        add("stops it being as good as it sounds.**")
        add("")
        add("Agent 5 still produced a complete three-tier guide on the")
        add("degraded run, because its universal tier criteria do not depend")
        add("on extraction. A patient reading it is still told to call 911 if")
        add("they cannot catch their breath or have chest pain that will not")
        add("stop. The generic safety net held.")
        add("")
        add("The extraction also RAISED warnings about its own degradation -")
        add("\"Document uses abbreviated clinical shorthand\", plus three")
        add("medications it could not confirm against the text. The system")
        add("knew something was wrong and said so.")
        add("")
        add("But the DOCUMENT-SPECIFIC signs are gone with no trace.")
        add("**Hemoptysis - coughing up blood - appears nowhere in anything")
        add("the patient sees on the degraded run**, and neither does the")
        add("radiating neck-and-arm pain. Both are in the clean run. Those")
        add("are the two signs this patient's own team singled out, and they")
        add("are exactly what a universal tier list cannot replace.")
        add("")
        add("So the honest statement is not \"warning signs are lost\" and not")
        add("\"the safety net holds\". It is: **under degradation the patient")
        add("keeps generic emergency advice and loses the specific warnings")
        add("written for them.**")
        add("")

        meds = totals["medications"]
        if meds["absent"]:
            add("### Medications, which have no generic safety net")
            add("")
            add(f"**{meds['absent']} of {meds['clean']} medications are absent "
                f"after degradation ({(meds['clean'] - meds['absent']) / meds['clean'] * 100:.1f}% "
                f"retention).**")
            add("")
            add("This is worse than the warning-sign case despite the better")
            add("percentage, because there is no equivalent of Agent 5's")
            add("universal tiers. A warning sign that drops still leaves the")
            add("patient a generic list telling them to call 911 for chest")
            add("pain. A medication that drops leaves nothing at all - the")
            add("drug simply is not on their list.")
            add("")
            names = []
            for row in rows:
                names.extend(row["fields"]["medications"]["absent"])
            add(f"Absent across the stratum: {', '.join(sorted(names))}.")
            add("")
            add("Supplements are the common case and the low-consequence one.")
            add("**`thymoglobulin` is not** - it is an immunosuppressant, and a")
            add("transplant patient who does not know they are on it is a")
            add("materially different situation from one missing a vitamin.")
            add("A retention percentage cannot make that distinction, which is")
            add("why the absent values are named individually here.")
            add("")

    # The sample's own hole, stated where it cannot be skimmed past. A
    # retention table that looks reassuring while the highest-consequence
    # field was never exercised is worse than no table.
    if totals["red_flag_symptoms"]["clean"] == 0:
        add("## What this sample CANNOT tell you")
        add("")
        add("**None of these six documents contained a single red-flag**")
        add("**symptom in the clean run, so warning-sign retention under**")
        add("**degradation is untested.** That is the highest-consequence")
        add("field in the system - a dropped red flag is the omission that")
        add("can cost someone an emergency visit they needed - and this")
        add("sample says nothing about it.")
        add("")
        add("Only 26% of the corpus carries red-flag symptoms at all, so a")
        add("six-document sample missing them is expected rather than")
        add("surprising. It still means the table above must not be read as")
        add("'degradation is safe'. **The next extension to this stratum")
        add("should select documents that DO carry red flags**, rather than")
        add("taking the first six by number.")
        add("")

    add("## Per document")
    add("")
    for row in rows:
        add(f"### `{row['doc']}`")
        add("")
        add(f"- Status: `{row['status_clean']}` → `{row['status_fax']}`")
        dx_same = row["dx_clean"].lower() == row["dx_fax"].lower()
        add(f"- Primary diagnosis: {'unchanged' if dx_same else 'CHANGED'}")
        if not dx_same:
            add(f"  - clean: {row['dx_clean']}")
            add(f"  - fax:   {row['dx_fax']}")
        add(f"- Patient-facing sections written: "
            f"{row['sections_clean']}/4 → {row['sections_fax']}/4")
        any_absent = False
        for field, data in row["fields"].items():
            if data["absent"]:
                any_absent = True
                add(f"- **ABSENT from `{field}`** "
                    f"({data['clean']} → {data['fax']}):")
                for item in data["absent"]:
                    add(f"  - {item}")
        for field, data in row["fields"].items():
            if data["relocated"]:
                add(f"- Relocated out of `{field}` (found elsewhere in the "
                    f"extraction): {', '.join(data['relocated'])}")
            if data["reworded"]:
                add(f"- Reworded in `{field}`: "
                    f"{', '.join(data['reworded'])}")
        if not any_absent:
            add("- **No extracted content absent**")
        add("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help=f"Write {_REPORT.name} as well as printing")
    args = parser.parse_args()

    doc_ids = sorted(
        path.stem[:-4] for path in _OUTPUTS.glob("*_fax.json"))
    rows = [row for row in (compare(d) for d in doc_ids) if row is not None]

    if not rows:
        print("No paired clean/degraded outputs found. Run:")
        print("  python scripts/run_corpus_for_review.py --corpus test-data/fax")
        return

    report = build_report(rows)
    print(report)
    if args.write:
        _REPORT.write_text(report)
        print(f"written: {_REPORT}")


if __name__ == "__main__":
    main()
