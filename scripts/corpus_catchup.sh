#!/usr/bin/env bash
#
# scripts/corpus_catchup.sh
#
# Fill in whatever the corpus run and the audio generation still owe, then
# refresh the accuracy report. Owner: Likitha Shankar.
#
# Written to be run unattended by cron, so it is IDEMPOTENT and SELF-LIMITING:
# when every document has an output and every diagnosis has an audio file, it
# logs "nothing to do" and exits without spending a single API call. That is
# what makes a daily schedule safe - it stops costing anything the day the
# work is finished, rather than needing someone to remember to remove it.
#
# Both jobs are quota-bound rather than time-bound:
#   - Vertex 429s within three documents without --delay, hence the pacing.
#   - Gemini TTS has a separate daily free-tier ceiling, so audio may fail
#     even when the corpus succeeds. Each is attempted independently.
#
# It deliberately does NOT commit or push. A human reviews what it produced.
#
# Usage:
#   ./scripts/corpus_catchup.sh              # run now
#   crontab -l                               # see the schedule
#
# Logs land in logs/corpus_catchup/<date>.log (gitignored).

set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

PY="$REPO/.venv/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3)"

LOG_DIR="$REPO/logs/corpus_catchup"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y%m%d).log"
exec >> "$LOG" 2>&1

echo "=============================================================="
echo "corpus catch-up $(date '+%Y-%m-%d %H:%M:%S')"

export LLM_PROVIDER=vertex
export VERTEX_PROJECT=dischargeiq-502723
export VERTEX_LOCATION=us-central1
# No paid fallback on an unattended job: a Vertex outage must not silently
# start spending on Anthropic overnight.
export LLM_FALLBACK_PROVIDER=none

missing() {
  "$PY" - <<'PYEOF'
import glob, pathlib
have = {pathlib.Path(f).stem for f in glob.glob('evaluation/corpus_outputs/mtsamples_*.json')}
docs = {pathlib.Path(f).stem for f in glob.glob('test-data/mtsamples/*.pdf')}
print(len(docs - have))
PYEOF
}

TODO="$(missing)"
echo "corpus outputs missing: $TODO"

if [ "$TODO" -gt 0 ]; then
  # 40 per night keeps a single run inside the daily quota; the script skips
  # documents that already have an output, so consecutive nights make progress
  # without redoing work.
  "$PY" scripts/run_corpus_for_review.py --limit 40 --delay 30
  echo "corpus outputs missing after run: $(missing)"
  "$PY" scripts/corpus_accuracy_report.py
else
  echo "corpus complete - no API calls made"
fi

# Per-case audio: one file per target diagnosis, generated from the most
# complete real analysis of that type. Separate quota, so attempt regardless.
AUDIO_TODO=0
for kind in heart_failure copd diabetes hip_replacement surgical; do
  [ -f "dischargeiq/media/$kind.wav" ] && continue
  AUDIO_TODO=1
  SRC="$("$PY" - "$kind" <<'PYEOF'
import glob, json, sys
want = sys.argv[1]
best, score = None, -1
for f in sorted(glob.glob('evaluation/corpus_outputs/mtsamples_*.json')):
    d = json.load(open(f))
    if d.get('document_type') != want or d.get('pipeline_status') == 'partial':
        continue
    s = sum(len(str(d.get(k) or '')) for k in
            ('diagnosis_explanation', 'medication_rationale',
             'recovery_trajectory', 'escalation_guide'))
    if s > score:
        best, score = f, s
print(best or '')
PYEOF
)"
  if [ -n "$SRC" ]; then
    echo "audio: $kind <- $SRC"
    "$PY" scripts/generate_case_audio.py "$SRC" || echo "  audio failed for $kind (quota?)"
    sleep 20
  else
    echo "audio: $kind has no usable source output yet"
  fi
done
[ "$AUDIO_TODO" -eq 0 ] && echo "all five audio files present - nothing to generate"

echo "done $(date '+%H:%M:%S')"
