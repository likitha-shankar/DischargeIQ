#!/usr/bin/env python3
"""
scripts/model_canary.py

Detect a change in the model behind a pinned name. Owner: Likitha Shankar.

THE PROBLEM
-----------
`gemini-2.5-flash-lite` is a moving target. Google can update the served
checkpoint without the name changing, and nothing in the response says which
one answered: `system_fingerprint` comes back empty and `response.model` just
echoes the request. Probed 10 Sep 2026.

So `docs/MODEL_VERSIONING.md` documents a re-evaluation trigger on version
change, and there is no version to trigger on. The corpus run is the only
thing that would notice, and only when somebody regenerates.

WHAT THIS DOES
--------------
Sends a small fixed prompt at temperature 0 and hashes the reply. Measured
before building it: five runs of the same probe produced ONE distinct output,
so the signal is stable enough that a change means something rather than
being noise.

A changed hash does NOT prove the model changed - it proves BEHAVIOUR changed,
which is the thing actually worth knowing. It is a smoke alarm, not a version
string.

WHY THE PROBES ARE SYNTHETIC
----------------------------
The first draft used a medication line copied verbatim from mtsamples_026,
which would have committed de-identified corpus text to the repository - the
exact mistake that made this repo's history a problem on 6 Sep 2026. Every
probe below is invented. They are shaped like clinical text and are not
clinical text.

Usage:
  python scripts/model_canary.py --freeze   # record today's behaviour
  python scripts/model_canary.py            # compare against it
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO / ".env")

from dischargeiq.utils.llm_client import get_llm_client  # noqa: E402

_BASELINE = _REPO / "evaluation" / "model_canary.json"

#: Fixed probes, each aimed at a behaviour this pipeline depends on.
#:
#: INVENTED text throughout - no line here comes from a real document. Drug
#: names are real drugs in fictional combinations, which is what makes the
#: probe meaningful without putting corpus content in the repository.
_PROBES = {
    # The behaviour the 10 Sep regression touched: reading every item from one
    # comma-separated list, including the ones after a qualifier.
    "list_extraction": (
        "Return ONLY a JSON array of the drug names in this line, in order, "
        "no other text: 'on admission, ibuprofen, ranitidine, allopurinol, "
        "cetirizine, spironolactone, and gabapentin.'"
    ),
    # Refusal behaviour: the model must not supply a value that is absent.
    "absent_field": (
        "From this line only, what is the discharge weight? Answer in under "
        "ten words. 'Patient seen in clinic. Blood pressure stable.'"
    ),
    # Instruction adherence on a structural constraint.
    "format_adherence": (
        "Reply with exactly three words and nothing else: name three colours."
    ),
}


def _digest(text: str) -> str:
    """Stable short digest of a reply, whitespace-normalised."""
    cleaned = " ".join((text or "").split())
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


def run_probes() -> dict:
    """
    Send every probe once and return its digest and reply.

    Returns:
        dict: probe name -> {"digest": str, "reply": str}. The reply is kept
        so a changed digest can be read rather than merely counted - a hash
        that moves with no way to see what moved is an alarm nobody can act on.
    """
    client, model = get_llm_client()
    results = {}
    for name, prompt in _PROBES.items():
        response = client.chat.completions.create(
            model=model,
            max_tokens=200,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        reply = (response.choices[0].message.content or "").strip()
        results[name] = {"digest": _digest(reply), "reply": reply}
    return {
        "provider": os.environ.get("LLM_PROVIDER", "gemini"),
        "model": model,
        "probes": results,
    }


def freeze() -> int:
    """Record current behaviour as the baseline."""
    current = run_probes()
    _BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    print(f"  froze {len(current['probes'])} probe(s) for {current['model']}")
    for name, entry in sorted(current["probes"].items()):
        print(f"    {name:18} {entry['digest']}")
    print(f"\n  {_BASELINE.relative_to(_REPO)}")
    print("  Replies are stored alongside the digests so a future change can "
          "be read, not just counted.")
    return 0


def check() -> int:
    """Compare current behaviour against the baseline. Returns drift count."""
    if not _BASELINE.exists():
        print("  no baseline - run with --freeze first")
        return 0
    baseline = json.loads(_BASELINE.read_text())
    current = run_probes()

    if baseline.get("model") != current["model"]:
        print(f"  MODEL NAME CHANGED: {baseline.get('model')} -> "
              f"{current['model']}")
        print("  That is a deliberate change on our side, not a served-model "
              "drift. Re-freeze if intended.")
        return 1

    drifted = 0
    for name, entry in sorted(current["probes"].items()):
        was = (baseline.get("probes") or {}).get(name, {})
        if was.get("digest") == entry["digest"]:
            print(f"  ok    {name}")
            continue
        drifted += 1
        print(f"  DRIFT {name}")
        print(f"        was: {was.get('reply', '(not in baseline)')!r}")
        print(f"        now: {entry['reply']!r}")

    print()
    if drifted:
        print(f"  {drifted} probe(s) changed on an unchanged model name.")
        print("  The served checkpoint behind the name has probably moved.")
        print("  Re-run the corpus before quoting any accuracy figure, and see")
        print("  docs/MODEL_VERSIONING.md for the re-evaluation trigger.")
    else:
        print("  No drift. The model behind the name behaves as it did.")
    return drifted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true",
                        help="record current behaviour as the baseline")
    args = parser.parse_args()
    print("=" * 62)
    print("DischargeIQ - served-model canary")
    print("=" * 62)
    if args.freeze:
        return freeze()
    return 1 if check() else 0


if __name__ == "__main__":
    sys.exit(main())
