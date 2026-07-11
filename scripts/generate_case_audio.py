"""
scripts/generate_case_audio.py

CLI for the per-case audio prototype (Task 2.5): turn one pipeline output
JSON into a two-host WAV explainer via dischargeiq.utils.case_audio.

Usage:
    # From a frozen review output, into the /media slot for its diagnosis:
    python scripts/generate_case_audio.py evaluation/corpus_outputs/heart_failure_01.json

    # Explicit destination:
    python scripts/generate_case_audio.py <payload.json> --out dischargeiq/media/heart_failure.wav

    # Script only (no TTS call, no quota) - review the dialogue text first:
    python scripts/generate_case_audio.py <payload.json> --script-only

Requires GOOGLE_API_KEY in .env. Two model calls total per run (one chat for
the script, one TTS for the audio) unless --script-only. Any audio intended
for patients still needs the Task 4.2 listen-through before shipping.
"""

import argparse
import json
import sys
from pathlib import Path

# Make `dischargeiq` importable when launched directly from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from dischargeiq.utils.case_audio import build_dialogue_script, synthesize_dialogue  # noqa: E402

_MEDIA_DIR = Path("dischargeiq/media")


def main() -> int:
    """Parse args, build the script, optionally synthesize, report the result."""
    parser = argparse.ArgumentParser(description="Generate a per-case audio explainer.")
    parser.add_argument("payload", help="Path to a PipelineResponse JSON (e.g. evaluation/corpus_outputs/*.json)")
    parser.add_argument("--out", help="Output WAV path; default: dischargeiq/media/<document_type>.wav")
    parser.add_argument("--script-only", action="store_true", help="Print the dialogue script and stop (no TTS call)")
    args = parser.parse_args()

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))

    script = build_dialogue_script(payload)
    print("=== dialogue script ===")
    print(script)
    if args.script_only:
        return 0

    doc_type = payload.get("document_type") or "unknown"
    out = Path(args.out) if args.out else _MEDIA_DIR / f"{doc_type}.wav"
    if doc_type == "unknown" and not args.out:
        print("document_type is 'unknown' - pass --out explicitly (no /media slot for unknown).")
        return 1
    path = synthesize_dialogue(script, out)
    print(f"\nAudio written: {path} - listen before shipping (Task 4.2).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
