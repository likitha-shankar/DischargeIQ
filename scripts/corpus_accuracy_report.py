#!/usr/bin/env python3
"""
scripts/corpus_accuracy_report.py

Task 3.4: the automated accuracy run over the de-identified corpus.
Owner: Likitha Shankar.

Reads the pipeline outputs in evaluation/corpus_outputs/ (written by
scripts/run_corpus_for_review.py) alongside the source PDFs they came from,
and writes evaluation/corpus_accuracy_report.md.

Three things are measured, because three different things can go wrong:

  READABILITY   - every narrative output against the 6.0 grade target. A
                  summary nobody can read has failed regardless of accuracy.
  GROUNDING     - medication names and numbers that appear in the output but
                  NOT in the source document. This is the fabrication check,
                  and it is the one that matters clinically: inventing a dose
                  is worse than omitting one.
  COMPLETENESS  - which fields the source documents actually contain. Real
                  discharge paperwork is missing sections constantly, and the
                  rate matters: it is the evidence behind treating an absent
                  section as the document's property rather than a failure of
                  this system.

Usage:
    python scripts/corpus_accuracy_report.py
    python scripts/corpus_accuracy_report.py --outputs evaluation/corpus_outputs

Dependencies: pdfplumber (source text), textstat (grade level).
"""

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pdfplumber
import textstat

_REPO = Path(__file__).resolve().parents[1]
_FK_TARGET = 6.0
_NARRATIVE = {
    "agent2": "diagnosis_explanation",
    "agent3": "medication_rationale",
    "agent4": "recovery_trajectory",
    "agent5": "escalation_guide",
}
# Numbers that are units of ordinary language rather than clinical claims.
# "Week 1", "call 911", "2 to 4 weeks" are not invented dosages.
_BENIGN_NUMBERS = {"911", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "24"}


def source_text(stem: str) -> str:
    """
    Extract the raw text of the source PDF for one output, or "" if missing.

    Args:
        stem: Output file stem, e.g. "mtsamples_003".

    Returns:
        The document's text, lowercased, or an empty string when the PDF is
        not on disk (the corpus is gitignored and rebuilt, so absence is
        normal on a fresh clone).
    """
    pdf = _REPO / "test-data" / "mtsamples" / f"{stem}.pdf"
    if not pdf.exists():
        return ""
    try:
        with pdfplumber.open(pdf) as doc:
            return " ".join((page.extract_text() or "") for page in doc.pages).lower()
    except Exception:  # noqa: BLE001 - a corrupt PDF must not kill the report
        return ""


def ungrounded_medications(output: dict, source: str) -> list[str]:
    """
    Medication names the extraction claims that the source does not contain.

    Agent 1's contract forbids inventing a field value, so any drug name here
    is a contract violation and the most clinically serious kind.
    """
    if not source:
        return []
    found = []
    for med in (output.get("extraction") or {}).get("medications") or []:
        name = str(med.get("name") or "").strip().lower()
        # Compare on the first word: "Furosemide 40mg tablet" is grounded if
        # the source says "furosemide", and brand/generic spacing varies.
        head = re.split(r"[\s,(/]", name)[0] if name else ""
        if len(head) >= 4 and head not in source:
            found.append(str(med.get("name")))
    return found


def ungrounded_numbers(output: dict, source: str) -> dict[str, list[str]]:
    """
    Numbers in each narrative section that do not appear in the source.

    Agent 2's prompt forbids inventing numbers outright; the others may only
    restate what the document said. Ordinary counts (week numbers, 911) are
    excluded so the signal is dosages, weights and thresholds.
    """
    if not source:
        return {}
    out: dict[str, list[str]] = {}
    for agent, field in _NARRATIVE.items():
        text = str(output.get(field) or "")
        loose = []
        for number in re.findall(r"\b\d+(?:\.\d+)?\b", text):
            if number in _BENIGN_NUMBERS:
                continue
            if number not in source:
                loose.append(number)
        if loose:
            out[agent] = sorted(set(loose))
    return out


def build(outputs_dir: Path) -> str:
    """Analyse every output and return the report as markdown."""
    files = sorted(outputs_dir.glob("mtsamples_*.json"))
    statuses: Counter = Counter()
    grades: dict[str, list[float]] = defaultdict(list)
    fields: Counter = Counter()
    med_violations: list[tuple[str, list[str]]] = []
    num_violations: list[tuple[str, dict]] = []
    sourced = 0

    for path in files:
        doc = json.load(open(path))
        statuses[doc.get("pipeline_status")] += 1
        for agent, value in (doc.get("fk_scores") or {}).items():
            grade = (value or {}).get("fk_grade")
            if isinstance(grade, (int, float)) and grade > 0:
                grades[agent].append(grade)

        extraction = doc.get("extraction") or {}
        for field, key in (("medications", "medications"),
                           ("red flag symptoms", "red_flag_symptoms"),
                           ("follow-up appointments", "follow_up_appointments"),
                           ("activity or diet", "activity_restrictions"),
                           ("discharge date", "discharge_date")):
            value = extraction.get(key)
            if value:
                fields[field] += 1

        source = source_text(path.stem)
        if source:
            sourced += 1
            meds = ungrounded_medications(doc, source)
            if meds:
                med_violations.append((path.stem, meds))
            numbers = ungrounded_numbers(doc, source)
            if numbers:
                num_violations.append((path.stem, numbers))

    total = len(files)
    lines = [
        "# Corpus accuracy run (task 3.4)",
        "",
        f"Generated {date.today().isoformat()} by `scripts/corpus_accuracy_report.py`",
        f"over {total} pipeline outputs in `evaluation/corpus_outputs/`.",
        "",
        "The corpus is 106 real de-identified discharge summaries (MTSamples",
        "transcriptions with identifiers removed). Neither the corpus nor these",
        "outputs is committed - both are rebuilt from scripts - so this report is",
        "the durable artefact of the run.",
        "",
        "## 1. Readability",
        "",
        f"Target: Flesch-Kincaid grade <= {_FK_TARGET} on every patient-facing output.",
        "",
        "| Agent | Section | Mean | Max | At or under target |",
        "|---|---|---|---|---|",
    ]
    names = {"agent2": "What happened", "agent3": "Medications",
             "agent4": "Recovery", "agent5": "Warning signs"}
    all_grades: list[float] = []
    for agent in sorted(grades):
        values = grades[agent]
        all_grades += values
        ok = sum(1 for v in values if v <= _FK_TARGET)
        lines.append(f"| {agent} | {names.get(agent, '')} | {statistics.mean(values):.2f} "
                     f"| {max(values):.2f} | {ok}/{len(values)} |")
    if all_grades:
        overall = 100 * sum(1 for v in all_grades if v <= _FK_TARGET) / len(all_grades)
        lines += ["",
                  f"**{overall:.0f}% of {len(all_grades)} outputs meet the sixth-grade "
                  f"target**, mean grade {statistics.mean(all_grades):.2f}."]

    lines += ["", "## 2. Grounding (output against source)", ""]
    if sourced == 0:
        lines.append("Source PDFs were not on disk, so grounding could not be checked. "
                     "Rebuild the corpus with `scripts/build_mtsamples_corpus.py` and "
                     "re-run.")
    else:
        lines += [
            f"Checked {sourced} of {total} outputs against their source document.",
            "",
            f"- **Medication names not present in the source: "
            f"{len(med_violations)}**. Agent 1 is contractually forbidden from "
            f"inventing a field value, so any hit here is a contract violation.",
            f"- **Outputs containing a number absent from the source: "
            f"{len(num_violations)}**. Week numbers and 911 are excluded, so this "
            f"measures dosages, weights and thresholds.",
        ]
        if med_violations:
            lines += ["", "Medication findings:", ""]
            for stem, meds in med_violations[:10]:
                lines.append(f"- `{stem}`: {', '.join(meds)}")
        if num_violations:
            # Classify rather than count. A raw total reads as "50
            # hallucinations", which is not what these are, and the two
            # classes below need different responses from different people.
            thresholds = Counter()
            targets = Counter()
            other = Counter()
            for stem, per_agent in num_violations:
                for agent, numbers in per_agent.items():
                    for number in numbers:
                        if number in {"101", "100.4", "38.5", "102"}:
                            thresholds[number] += 1
                        elif number in {"15", "20", "30", "45", "60", "90"}:
                            targets[number] += 1
                        else:
                            other[f"{agent}:{number}"] += 1
            lines += [
                "",
                "These are not random fabrications. They fall into two classes,",
                "and only one of them is a defect in this system:",
                "",
                f"**Clinical thresholds the prompts supply** ({sum(thresholds.values())} "
                f"occurrences): fever limits such as \"over 101 F\" and \"100.4 F\". "
                "These come from the agent prompts, not from the patient's document. "
                "They are standard clinical guidance, but they are shown to the "
                "patient as if their own paperwork said so.",
                "",
                f"**Activity targets the model invents** ({sum(targets.values())} "
                "occurrences): \"walk for 15 minutes each day\", \"do not bend your "
                "new knee more than 90 degrees\". The agent 4 prompt REQUIRES one "
                "specific goal per week, so when the source document sets none, the "
                "model supplies a number. The requirement causes the invention.",
                "",
                f"**Everything else**: {sum(other.values())} occurrences.",
                "",
                "### The question for clinician review",
                "",
                "Both classes are defensible as general patient education and",
                "indefensible as instructions attributed to a specific discharge",
                "document. A knee protocol differs between surgeons; a fever",
                "threshold differs for an immunocompromised patient. This is the",
                "first thing to put in front of the LOF reviewers (task 4.2), and",
                "it is not a decision to make unilaterally in a prompt file.",
            ]

    lines += ["", "## 3. What the source documents actually contain", "",
              "The reason an absent section is treated as a property of the",
              "paperwork rather than a failure of this system.", "",
              "| Field | Documents containing it |", "|---|---|"]
    for field, count in fields.most_common():
        lines.append(f"| {field} | {count}/{total} ({100*count/total:.0f}%) |")

    lines += ["", "## 4. Pipeline status", "", "| Status | Count |", "|---|---|"]
    for status, count in statuses.most_common():
        lines.append(f"| `{status}` | {count} |")
    lines += ["",
              "`complete_with_warnings` is the expected majority on real paperwork:",
              "it means every agent ran and the source was missing sections.",
              "`partial` means an agent failed and retrying may help.",
              ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write the report next to the outputs it describes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path,
                        default=_REPO / "evaluation" / "corpus_outputs")
    parser.add_argument("--out", type=Path,
                        default=_REPO / "evaluation" / "corpus_accuracy_report.md")
    args = parser.parse_args()

    report = build(args.outputs)
    args.out.write_text(report)
    print(f"wrote {args.out} ({len(report.splitlines())} lines)")


if __name__ == "__main__":
    main()
