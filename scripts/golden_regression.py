#!/usr/bin/env python3
"""
scripts/golden_regression.py

Golden-file regression over the corpus. Owner: Likitha Shankar.

Closes the last open item in Liebovitz 3.5 ("golden-file regression tests over
the corpus"), which was the only remaining engineering-hygiene item that
blocked on nobody.

WHY THE OBVIOUS DESIGN DOES NOT WORK
------------------------------------
A golden-file test normally freezes exact output and diffs against it. Two
things rule that out here.

First, the outputs are LLM prose. Regenerating `diagnosis_explanation` on an
unchanged document produces different words, so an exact diff would fail every
run and be switched off within a week. What must stay stable is not the
wording but the FACTS: which medications, how many appointments, whether the
escalation guide still routes to 911.

Second, the corpus is de-identified clinical text and `evaluation/corpus_outputs/`
is gitignored under the program rule. A committed golden file full of
medication names and dates would put clinical content back in the repository -
the exact mistake that made this repo's history a problem on 6 Sep 2026.

WHAT THIS DOES INSTEAD
----------------------
Two artefacts, with different jobs and different visibility:

  evaluation/golden/*.json          GITIGNORED. Full per-document detail,
                                    including entity names. Regenerable.
                                    Tells you WHAT changed.

  evaluation/golden_manifest.json   COMMITTED. Carries no clinical text at
                                    all - counts, statuses, booleans, and
                                    SHA-256 digests of normalised entity
                                    sets. Tells you THAT something changed,
                                    inside a code review.

The manifest is the regression gate. A reviewer sees a digest move in a diff
and knows extraction behaviour changed on that document, without ever reading
a patient's medication list. The local goldens turn that into a name.

Usage:
  python scripts/golden_regression.py --freeze    # after a deliberate change
  python scripts/golden_regression.py             # check for drift
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_OUTPUTS = _REPO / "evaluation" / "corpus_outputs"
_GOLDEN_DIR = _REPO / "evaluation" / "golden"
_MANIFEST = _REPO / "evaluation" / "golden_manifest.json"

#: Prose sections whose WORDING is allowed to drift but whose properties are
#: not. Hashing these would guarantee a failing run on every regeneration.
_PROSE = [
    "diagnosis_explanation",
    "medication_rationale",
    "recovery_trajectory",
    "escalation_guide",
]

#: How far a reading grade may move before it counts as drift. Regenerated
#: prose moves a little; a full grade level is a behaviour change.
_FK_TOLERANCE = 1.0


def _digest(values: list[str]) -> str:
    """
    Stable digest of a set of entity strings.

    Normalised - lowercased, whitespace collapsed, sorted - so that reordering
    or re-spacing does not read as a content change. Truncated to 16 hex
    characters: enough to make a collision irrelevant here, short enough that
    a manifest diff stays readable.
    """
    cleaned = sorted(re.sub(r"\s+", " ", str(v)).strip().lower()
                     for v in values if str(v).strip())
    joined = "|".join(cleaned)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _entity_lists(extraction: dict) -> dict[str, list[str]]:
    """The extracted entities worth pinning, as flat string lists."""
    medications = extraction.get("medications") or []
    appointments = extraction.get("follow_up_appointments") or []
    return {
        # Name and dose together: a dose that silently changes matters as much
        # as a drug that disappears, and Liebovitz weights doses explicitly.
        "medications": [f"{m.get('name')}|{m.get('dose')}"
                        for m in medications if isinstance(m, dict)],
        "appointments": [f"{a.get('specialty') or a.get('provider')}|{a.get('date')}"
                         for a in appointments if isinstance(a, dict)],
        "red_flags": list(extraction.get("red_flag_symptoms") or []),
        "secondary_diagnoses": list(extraction.get("secondary_diagnoses") or []),
        "procedures": list(extraction.get("procedures_performed") or []),
    }


def summarise(payload: dict) -> dict:
    """
    Reduce one pipeline output to the properties a regression should pin.

    Returns:
        dict: Counts, statuses, booleans, reading grades and entity digests.
        Contains NO clinical free text - verified by
        `manifest_carries_no_clinical_text` below.
    """
    extraction = payload.get("extraction") or {}
    entities = _entity_lists(extraction)
    guide = payload.get("escalation_guide") or ""

    return {
        "pipeline_status": payload.get("pipeline_status"),
        "document_type": payload.get("document_type"),
        "source_stratum": payload.get("source_stratum"),
        "source_degraded": bool(payload.get("source_degraded")),
        "counts": {name: len(values) for name, values in entities.items()},
        "digests": {name: _digest(values) for name, values in entities.items()},
        # Presence, not content. An empty patient-facing section is the
        # failure test_patient_facing_never_empty.py exists for; this catches
        # it drifting back in on a specific document.
        "sections_present": {name: bool((payload.get(name) or "").strip())
                             for name in _PROSE},
        "fk": {agent: round(float(grade), 1)
               for agent, grade in sorted((payload.get("fk_scores") or {}).items())
               if isinstance(grade, (int, float))},
        # Agent 5's contract: all three tiers regardless of source content.
        "escalation_routes_to_911": "911" in guide,
        "escalation_tiers": sum(
            marker in guide.upper()
            for marker in ("911", "ER TODAY", "CALL YOUR DOCTOR")),
    }


def _load_outputs() -> dict[str, dict]:
    """
    Every COMPLETED corpus output, by document id.

    Partial and rejected runs are excluded from both freezing and checking. A
    partial is a transient failure - a 429, a timeout, a dead provider - so
    pinning one would freeze an outage as the expected behaviour and then
    report drift the moment it succeeded.

    Worth stating because it is invisible until it bites: a document that is
    partial at freeze time is in neither the manifest nor the check, so a
    regression on it is not detected. Sabotaging `copd_02` during testing
    produced no drift for exactly this reason, which read as a hole in the
    tool until the status explained it. Of 135 outputs, 134 are frozen.
    """
    found = {}
    for path in sorted(_OUTPUTS.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if payload.get("pipeline_status") in ("complete", "complete_with_warnings"):
            found[path.stem] = payload
    return found


def freeze() -> int:
    """Write the goldens and the manifest from the current outputs."""
    outputs = _load_outputs()
    if not outputs:
        print("no corpus outputs found - run scripts/run_corpus_for_review.py")
        return 1

    _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for doc_id, payload in outputs.items():
        summary = summarise(payload)
        manifest[doc_id] = summary
        # The local golden additionally carries the entity NAMES, which is
        # what turns "a digest moved" into "furosemide disappeared". Never
        # committed; see the module docstring.
        (_GOLDEN_DIR / f"{doc_id}.json").write_text(json.dumps(
            {**summary, "entities": _entity_lists(payload.get("extraction") or {})},
            indent=2, sort_keys=True))

    _MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"froze {len(manifest)} documents")
    print(f"  {_MANIFEST.relative_to(_REPO)}  (committed, no clinical text)")
    print(f"  {_GOLDEN_DIR.relative_to(_REPO)}/  (gitignored, {len(manifest)} files)")
    return 0


def _compare(doc_id: str, expected: dict, actual: dict) -> list[str]:
    """Every drift between one document's golden and its current output."""
    drift = []

    for field in ("pipeline_status", "document_type", "source_stratum",
                  "source_degraded", "escalation_routes_to_911",
                  "escalation_tiers"):
        if expected.get(field) != actual.get(field):
            drift.append(f"{field}: {expected.get(field)!r} -> {actual.get(field)!r}")

    for name, was in (expected.get("counts") or {}).items():
        now = (actual.get("counts") or {}).get(name)
        if was != now:
            drift.append(f"count {name}: {was} -> {now}")

    for name, was in (expected.get("digests") or {}).items():
        now = (actual.get("digests") or {}).get(name)
        if was != now:
            # A digest change with an unchanged count means an entity was
            # SUBSTITUTED, not added or dropped - the quietest kind, and the
            # one a count-only check would miss entirely.
            same_count = ((expected.get("counts") or {}).get(name)
                          == (actual.get("counts") or {}).get(name))
            how = "content changed, count unchanged" if same_count else "content changed"
            drift.append(f"digest {name}: {how} ({was} -> {now})")

    for name, was in (expected.get("sections_present") or {}).items():
        now = (actual.get("sections_present") or {}).get(name)
        if was != now:
            drift.append(f"section {name} present: {was} -> {now}")

    for agent, was in (expected.get("fk") or {}).items():
        now = (actual.get("fk") or {}).get(agent)
        if now is None:
            drift.append(f"fk {agent}: {was} -> missing")
        elif abs(was - now) > _FK_TOLERANCE:
            drift.append(f"fk {agent}: {was} -> {now} (beyond ±{_FK_TOLERANCE})")

    return drift


def check() -> int:
    """Compare current outputs against the manifest. Returns drift count."""
    if not _MANIFEST.exists():
        print("no manifest - run with --freeze first")
        return 1
    manifest = json.loads(_MANIFEST.read_text())
    outputs = _load_outputs()
    if not outputs:
        print("no corpus outputs found - nothing to check against")
        return 1

    drifted, missing, added = {}, [], []

    for doc_id, expected in manifest.items():
        if doc_id not in outputs:
            missing.append(doc_id)
            continue
        drift = _compare(doc_id, expected, summarise(outputs[doc_id]))
        if drift:
            drifted[doc_id] = drift

    added = [d for d in outputs if d not in manifest]

    print(f"checked {len(manifest)} frozen documents against "
          f"{len(outputs)} current outputs\n")
    for doc_id, lines in sorted(drifted.items()):
        print(f"  DRIFT  {doc_id}")
        for line in lines:
            print(f"           {line}")
    if missing:
        print(f"\n  {len(missing)} frozen document(s) have no current output: "
              f"{missing[:5]}")
    if added:
        print(f"\n  {len(added)} new document(s) not in the manifest: "
              f"{added[:5]}\n  (re-freeze to adopt them)")

    total = len(drifted) + len(missing)
    print("\n" + "=" * 62)
    if total:
        print(f"{len(drifted)} document(s) drifted, {len(missing)} missing.")
        print("Re-freeze ONLY after confirming each change was intended.")
    else:
        print("No drift.")
    print("=" * 62)
    return total


def manifest_carries_no_clinical_text(manifest: dict) -> list[str]:
    """
    Every offending value in a manifest, empty when it is safe to commit.

    The whole design rests on the manifest being committable, so this is
    checked rather than asserted in a comment. Permitted leaf values are
    numbers, booleans, None, hex digests, and a short closed vocabulary of
    status and stratum labels. Anything else is potential clinical text.
    """
    allowed = {
        "complete", "complete_with_warnings", "partial", "rejected",
        "structured", "dictated", "scanned_fax", "multi_page", "unknown",
        "heart_failure", "copd", "diabetes", "hip_replacement",
        "surgical_case", "surgical", "other",
    }
    offenders = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")
        elif isinstance(node, str):
            if node in allowed:
                return
            if re.fullmatch(r"[0-9a-f]{16}", node):
                return
            offenders.append(f"{path}: {node!r}")

    walk(manifest)
    return offenders


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true",
                        help="rewrite the goldens from the current outputs")
    args = parser.parse_args()

    print("=" * 62)
    print("DischargeIQ - golden-file regression")
    print("=" * 62)

    if args.freeze:
        code = freeze()
        if code == 0:
            offenders = manifest_carries_no_clinical_text(
                json.loads(_MANIFEST.read_text()))
            if offenders:
                print("\nREFUSING: the manifest carries free text and must "
                      "not be committed:")
                for line in offenders[:10]:
                    print(f"  {line}")
                return 1
            print("  manifest verified free of clinical text")
        return code

    return 1 if check() else 0


if __name__ == "__main__":
    sys.exit(main())
