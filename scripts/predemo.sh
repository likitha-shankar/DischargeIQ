#!/usr/bin/env bash
#
# scripts/predemo.sh
#
# Run this 30 minutes before a live demo. Owner: Likitha Shankar.
#
# WHY THE TIMING MATTERS
# ----------------------
# Two things go cold and both are silent until the moment they bite:
#
#   The audio cache is PROCESS-LOCAL (media.py `_audio_cache`). A Cloud Run
#   instance restart empties it, and the first per-case audio press then costs
#   a script LLM call plus TTS - roughly 8 seconds of nothing happening while
#   Frank watches.
#
#   Vertex serves Gemini on DYNAMIC SHARED QUOTA. There is no reserved
#   capacity and no reset window, so a 429 is possible at any moment and
#   nothing here prevents one. As of 9 Sep 2026 the cross-provider failover is
#   DISABLED (LLM_FALLBACK_PROVIDER=none, RESTRICTED_DATA_MODE=1) because it
#   sent patient data to a provider outside the BAA. That was the right call
#   and it removes the safety net a 429 used to have: a throttled call now
#   ends as `partial` rather than quietly succeeding elsewhere.
#
# So this warms the path and tells you plainly whether to demo live or open
# the offline page.
#
# Usage:  ./scripts/predemo.sh

set -uo pipefail
cd "$(dirname "$0")/.."

BASE="https://dischargeiq-678599658918.us-central1.run.app/api"
API_KEY=$(grep -E '^DISCHARGEIQ_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"' \r")

echo "=============================================================="
echo " DischargeIQ pre-demo check"
echo "=============================================================="

# ── 1. Is the service up and is the BAA path active? ────────────────────────
echo
echo "1. Service"
health=$(curl -s -m 60 "$BASE/health")
echo "$health" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('   UNREACHABLE - demo from docs/demo_fallback.html'); raise SystemExit(1)
db = (d.get('database') or {}).get('reachable')
print(f\"   status={d.get('status')}  provider={d.get('llm_provider')}  db={db}\")
if d.get('llm_provider') != 'vertex':
    print('   WARNING: provider is not vertex - the BAA path is not active')
"

# ── 2. Warm the pipeline on the documents the demo actually uses ────────────
echo
echo "2. Warming the demo documents"
# /analyze is capped at 5 requests per minute per IP by our OWN limiter
# (middleware.py `_RATE_LIMITS`). Firing these back to back trips it, and a
# local 429 looks exactly like a Vertex 429 unless you notice it came back in
# a tenth of a second. Spaced out, and retried once, so the check reports the
# state of the SERVICE rather than the state of this script.
for doc in heart_failure_01 not_a_discharge_invoice; do
  printf "   %-26s " "$doc"
  for attempt in 1 2; do
    start=$(date +%s%N)
    code=$(curl -s -m 300 -X POST "$BASE/analyze" \
      -H "Authorization: Bearer $API_KEY" \
      -F "file=@test-data/$doc.pdf" \
      -o "/tmp/predemo_$doc.json" -w "%{http_code}")
    elapsed_ms=$(( ($(date +%s%N) - start) / 1000000 ))
    # A 429 back in under a second is ours, not upstream. Wait out the
    # window and try again rather than reporting a false alarm.
    if [[ "$code" == "429" && "$elapsed_ms" -lt 1000 && "$attempt" -eq 1 ]]; then
      printf "local rate limit, waiting 60s... "
      sleep 60
      continue
    fi
    break
  done
  if [[ "$code" != "200" ]]; then
    echo "HTTP $code  <-- demo from the offline page"
    continue
  fi
  python3 -c "
import json
d = json.load(open('/tmp/predemo_$doc.json'))
s = d.get('pipeline_status')
print(f'{s}' + ('  <-- 429 or agent failure, prefer the offline page' if s == 'partial' else ''))
"
done

# ── 3. Warm the audio cache ─────────────────────────────────────────────────
# The per-case explainer is the most fragile moment in the demo: cold, it is
# two model calls and about eight seconds of silence.
echo
echo "3. Warming the per-case audio"
if [[ -s /tmp/predemo_heart_failure_01.json ]]; then
  python3 -c "
import json
p = json.load(open('/tmp/predemo_heart_failure_01.json'))
json.dump({'session_id': p.get('pdf_session_id') or 'demo', 'pipeline_payload': p},
          open('/tmp/predemo_audio.json', 'w'))
"
  for pass_no in 1 2; do
    printf "   pass %s  " "$pass_no"
    curl -s -o /dev/null -m 180 -X POST "$BASE/media/case" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $API_KEY" \
      --data @/tmp/predemo_audio.json -w "HTTP %{http_code}  %{time_total}s\n"
    sleep 3
  done
  echo "   (pass 2 should be well under a second - that is the cache)"
fi

# ── 4. The offline page, which is the actual insurance ──────────────────────
echo
echo "3b. Per-condition audio vs its source"
python3 scripts/check_media_drift.py | sed 's/^/   /'
echo "   (DRIFTED or UNKNOWN means that condition's podcast says something the"
echo "    source no longer does - do not play it. The per-case audio is fine.)"

echo
echo "4. Offline fallback"
if [[ -f docs/demo_fallback.html ]]; then
  size=$(( $(wc -c < docs/demo_fallback.html) / 1024 ))
  echo "   docs/demo_fallback.html  ${size} KB  - open this if anything above misbehaves"
  echo "   Rebuild with: python scripts/build_demo_fallback.py"
else
  echo "   MISSING. Build it now: python scripts/build_demo_fallback.py"
fi

echo
echo "=============================================================="
echo " Demo the live path if section 2 says complete."
echo " Open docs/demo_fallback.html if anything says partial or 429."
echo "=============================================================="
