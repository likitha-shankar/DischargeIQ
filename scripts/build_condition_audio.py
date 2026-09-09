#!/usr/bin/env python3
"""
scripts/build_condition_audio.py

Regenerate a per-condition audio explainer from its source document, using the
project's own TTS rather than NotebookLM. Owner: Likitha Shankar.

WHY THIS EXISTS
---------------
The five per-condition WAVs were made BY HAND in NotebookLM. Nothing linked a
WAV to the markdown it came from, so editing a source changed what the audio
was supposed to say and left the audio saying the old thing.

That became real on 9 Sep 2026. The heart-failure explainer told every
listener to call their doctor after gaining more than two pounds in a day -
the ACC/AHA figure, correct in general - while the app showed that same
patient the threshold from their OWN summary, three pounds on the demo
document, with a more urgent action. The source was corrected to stop
competing with the patient's paperwork. Regenerating the audio then required
a person, a browser, and remembering to do it.

Same TTS path as POST /media/case (`synthesize_dialogue_bytes`, Google Cloud
TTS on ADC), so the audio is reproducible from source and the drift check can
be honoured with one command.

WHAT CHANGES, AND IT IS NOT NOTHING
-----------------------------------
NotebookLM produces a conversational podcast with interruptions and natural
back-and-forth. This produces a clean two-host read: correct, calm, and
flatter. That trade is worth making for content that must be re-derivable
from a reviewed source, but a listener will notice, and the Task 4.2
listen-through should judge the new files rather than assume the old
verdict carries over.

Usage:
  python scripts/build_condition_audio.py heart_failure surgical
  python scripts/build_condition_audio.py --all
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO / ".env")

from dischargeiq.utils.case_audio import synthesize_dialogue_bytes  # noqa: E402
from dischargeiq.utils.llm_client import (  # noqa: E402
    call_chat_with_fallback,
    get_llm_client,
    load_agent_prompt,
)
from dischargeiq.utils.scorer import fk_check  # noqa: E402

_MEDIA = _REPO / "dischargeiq" / "media"
_SOURCES = _MEDIA / "sources"

#: Numerals in a generic explainer are the defect this whole change is about.
#: A per-condition file has no patient document behind it, so any threshold it
#: states competes with the one in the listener's own paperwork.
_THRESHOLD = re.compile(
    r"\b(?:over|above|more than|greater than)\s+"
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
    re.IGNORECASE,
)


def _narratable(source: Path) -> str:
    """
    The parts of a source document meant to be spoken.

    HTML comments carry editorial notes to whoever maintains the file - the
    reasoning behind a removed threshold, for instance - and must never reach
    a listener. The narration-guidance and pronunciation sections are
    instructions ABOUT the reading, not part of it.
    """
    text = re.sub(r"<!--.*?-->", "", source.read_text(), flags=re.DOTALL)
    keep: list[str] = []
    skipping = False
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            skipping = heading.startswith(("how to narrate", "pronunciation"))
            if not skipping:
                keep.append(line)
            continue
        if not skipping and not line.startswith("# "):
            keep.append(line)
    return "\n".join(keep).strip()


def build_script(source: Path) -> str:
    """Turn one source document into a Sam/Alex dialogue script."""
    system_prompt = load_agent_prompt("tts_script_prompt.txt")
    client, model = get_llm_client()
    payload = {
        "audience": "patient",
        "explainer_for": source.stem.replace("_", " "),
        "content_to_narrate": _narratable(source),
        "note": (
            "This is a GENERAL explainer for a condition, not one patient's "
            "discharge summary. Do not state any numeric threshold, limit or "
            "target - the listener's own paperwork carries those and this "
            "file must not compete with it."
        ),
    }
    script = call_chat_with_fallback(
        client=client,
        model_name=model,
        system_prompt=system_prompt,
        user_message=json.dumps(payload),
        max_tokens=800,
        provider=os.environ.get("LLM_PROVIDER", "vertex"),
        agent_name="condition_audio",
        document_id=source.stem,
    ).strip()
    if "Sam:" not in script:
        raise ValueError(f"{source.stem}: model returned no speaker lines")
    return script


def verify(script: str, name: str) -> list[str]:
    """
    Check a generated script before it becomes audio.

    Returns:
        A list of problems. Empty means the script is safe to synthesize.
    """
    problems: list[str] = []
    found = _THRESHOLD.findall(script)
    if found:
        problems.append(f"states a numeric threshold ({', '.join(found)})")
    lowered = script.lower()
    for phrase in ("stop taking", "stop your", "skip a dose", "change your dose"):
        if phrase in lowered:
            problems.append(f'says "{phrase}"')
    grade = fk_check(script)["fk_grade"]
    if grade > 6.0:
        problems.append(f"reading grade {grade:.1f} exceeds 6.0")
    return problems


def regenerate(name: str) -> bool:
    """Build, verify and write one condition's audio. True on success."""
    source = _SOURCES / f"{name}.md"
    if not source.exists():
        print(f"  {name}: no source document")
        return False

    script = build_script(source)
    problems = verify(script, name)
    if problems:
        # Refuse rather than ship. Audio is optional; wrong audio is not.
        print(f"  {name}: REFUSED - {'; '.join(problems)}")
        print(f"    script was:\n{script}")
        return False

    wav = _MEDIA / f"{name}.wav"
    wav.write_bytes(synthesize_dialogue_bytes(script))
    (_MEDIA / f"{name}.script.txt").write_text(script + "\n")

    import hashlib
    (wav.with_suffix(".sha256")).write_text(
        hashlib.sha256(source.read_bytes()).hexdigest() + "\n")

    grade = fk_check(script)["fk_grade"]
    print(f"  {name}: {wav.stat().st_size // 1024} KB, "
          f"reading grade {grade:.1f}, source stamped")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="Condition names to rebuild")
    parser.add_argument("--all", action="store_true", help="Rebuild every one")
    args = parser.parse_args()

    names = ([p.stem for p in sorted(_SOURCES.glob("*.md"))]
             if args.all else args.names)
    if not names:
        parser.error("name at least one condition, or pass --all")

    print(f"Regenerating {len(names)} explainer(s) with the project's own TTS")
    ok = sum(regenerate(n) for n in names)
    print(f"\n{ok} of {len(names)} rebuilt")
    if ok:
        print("The Task 4.2 listen-through must judge these NEW files - the "
              "voice and pacing differ from the NotebookLM originals.")
    return 0 if ok == len(names) else 1


if __name__ == "__main__":
    sys.exit(main())
