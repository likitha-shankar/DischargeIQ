#!/usr/bin/env python3
"""
scripts/grounding_gate_readiness.py

Answers one question: if the post-hoc grounding verifier were enforcing today,
how much would it block? Owner: Likitha Shankar.

Item 3.2 of the Dr. Liebovitz faculty review asks for a hard failure when an
output contains an entity or number absent from the source. That is the right
end state. Turning it on before measuring is how a gate becomes a rubber stamp
or a bypassed nuisance, so this script is the evidence that has to come first.

It is also the lesson from 25 Aug 2026, when the sibling omission checker
reported six violations on its first corpus run and all six were false
positives. Measure, tune, then enforce.

Usage:
    python scripts/grounding_gate_readiness.py
    python scripts/grounding_gate_readiness.py --outputs evaluation/corpus_outputs

Reads existing pipeline outputs and their source PDFs. Makes NO API calls, so
it costs nothing and can be run as often as wanted.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "scripts"))

from corpus_accuracy_report import source_text  # noqa: E402 - path set above
from dischargeiq.utils.grounding import verify_output  # noqa: E402


def measure(outputs_dir: Path) -> dict:
    """
    Run the verifier over every available output and tally the result.

    Args:
        outputs_dir: Directory of pipeline output JSON files.

    Returns:
        A dict of counts plus the per-agent breakdown of invented values, which
        is what tells you which prompt to fix first.
    """
    checked = clean = would_block = would_block_invented = 0
    categories: Counter = Counter()
    by_agent: Counter = Counter()
    values: Counter = Counter()

    for path in sorted(outputs_dir.glob("mtsamples_*.json")):
        output = json.load(open(path))
        report = verify_output(output, source_text(path.stem))
        # An output with no source on disk was not checked. Counting it as
        # clean would be the exact dishonesty this script exists to avoid.
        if not report.source_available:
            continue
        checked += 1
        if report.is_clean:
            clean += 1
        else:
            would_block += 1
        if report.invented_findings:
            would_block_invented += 1
        for finding in report.findings:
            categories[finding.category] += 1
            if finding.category != "prompt_threshold":
                by_agent[finding.agent] += 1
                values[f"{finding.agent}:{finding.value}"] += 1

    return {
        "checked": checked,
        "clean": clean,
        "would_block": would_block,
        "would_block_invented": would_block_invented,
        "categories": dict(categories),
        "by_agent": dict(by_agent),
        "top_values": values.most_common(10),
    }


def main() -> None:
    """Print the readiness figures and a plain verdict on enforcement."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path,
                        default=_REPO / "evaluation" / "corpus_outputs")
    args = parser.parse_args()

    result = measure(args.outputs)
    checked = result["checked"] or 1

    print(f"checked                     {result['checked']}")
    print(f"clean                       {result['clean']}")
    print(f"would fail a hard gate      {result['would_block']} "
          f"({100 * result['would_block'] / checked:.0f}%)")
    print(f"  excluding prompt limits   {result['would_block_invented']} "
          f"({100 * result['would_block_invented'] / checked:.0f}%)")
    print(f"categories                  {result['categories']}")
    print(f"invented, by agent          {result['by_agent']}")
    print("most common invented values:")
    for label, count in result["top_values"]:
        print(f"    {label:24} {count}")

    # The verdict is the point. A percentage on its own invites someone to
    # enable the gate anyway and discover the consequences in production.
    blocked_pct = 100 * result["would_block"] / checked
    print()
    if blocked_pct > 10:
        print(f"VERDICT: do NOT enforce. {blocked_pct:.0f}% of documents would be")
        print("blocked. Fix the causes first - see invented-by-agent above - then")
        print("re-run this script. Enforcement is safe when this number is small")
        print("and every remaining case is a genuine defect.")
    else:
        print(f"VERDICT: {blocked_pct:.0f}% would be blocked. Review the remaining")
        print("cases individually; if each is a real defect, enforcement is ready.")


if __name__ == "__main__":
    main()
