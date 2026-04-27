#!/usr/bin/env bash
# File: start.sh
# Owner: Likitha Shankar
# Description: macOS/Linux dev bootstrap — creates .venv if needed, installs
#   requirements.txt, validates .env keys for the chosen LLM_PROVIDER, then starts
#   uvicorn (8000), Streamlit (8501), and optionally Flutter web (55497) in background.
# Usage: ./start.sh (from repo root, after chmod +x)
# Environment variables required: Reads .env (LLM_PROVIDER and provider API keys);
#   honors CLI_LLM_PROVIDER / CLI_LLM_MODEL overrides when sourcing .env.
# Edge cases: Exits with setup instructions if .env missing keys; Flutter optional;
#   waits only on backend+Streamlit so a failed Flutter start does not kill the stack;
#   Ctrl-C runs cleanup on child PIDs.

# DischargeIQ — one-command startup for macOS / Linux.
#
# What this does:
#   1. Creates .venv if missing and installs requirements.txt.
#   2. Verifies .env exists and that required API keys are non-empty.
#      Exits with clear instructions if any required key is missing.
#   3. Starts the FastAPI backend (uvicorn) on http://127.0.0.1:8000.
#   4. Starts the Streamlit frontend on http://127.0.0.1:8501.
#   5. Starts Flutter web app on http://127.0.0.1:55497 when available.
#   6. Ctrl-C stops all started services cleanly.

set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
VENV_DIR=".venv"
BACKEND_PORT=8000
FRONTEND_PORT=8501
FLUTTER_WEB_PORT=55497

banner() {
    echo "────────────────────────────────────────────────────────────"
    echo " DischargeIQ — startup"
    echo "────────────────────────────────────────────────────────────"
}

fail() {
    echo ""
    echo "ERROR: $1" >&2
    exit 1
}

banner

# ── 1. Python check ─────────────────────────────────────────────────
if ! command -v "$PY" >/dev/null 2>&1; then
    fail "$PY not found on PATH. Install Python 3.11+ and retry."
fi

PY_VERSION="$($PY -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "[start] Python: $PY_VERSION ($($PY -c 'import sys; print(sys.executable)'))"

# ── 2. Virtual env + deps ───────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "[start] Creating virtual environment in $VENV_DIR"
    "$PY" -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# Resolve a working venv interpreter explicitly. Prefer the standard venv
# entrypoints; fall back to python3.M (e.g. 3.12, 3.14) if shims are broken.
VENV_PY=""
for cand in "$VENV_DIR/bin/python" "$VENV_DIR/bin/python3"; do
    if [ -x "$cand" ]; then
        VENV_PY="$cand"
        break
    fi
done
if [ -z "$VENV_PY" ]; then
    for cand in "$VENV_DIR"/bin/python3.[0-9]*; do
        if [ -x "$cand" ]; then
            VENV_PY="$cand"
            break
        fi
    done
fi
if [ -z "$VENV_PY" ]; then
    fail "No executable Python found in $VENV_DIR/bin"
fi

echo "[start] Venv Python: $VENV_PY"

echo "[start] Installing requirements (quiet)"
"$VENV_PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt

# ── 3. .env validation ──────────────────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo ""
        echo "════════════════════════════════════════════════════════════"
        echo " .env created from .env.example."
        echo ""
        echo " ACTION REQUIRED — edit .env: set LLM_PROVIDER and the matching API key."
        echo "   All five agents use the same LLM_PROVIDER."
        echo ""
        echo " Typical keys (pick one path):"
        echo "   • ANTHROPIC_API_KEY   (if LLM_PROVIDER=anthropic, default — optional LLM_MODEL, see .env.example)"
        echo "   • OPENROUTER_API_KEY  (if LLM_PROVIDER=openrouter)"
        echo "   • OPENAI_API_KEY      (if LLM_PROVIDER=openai)"
        echo "   • (nothing)           (if LLM_PROVIDER=ollama, run locally)"
        echo ""
        echo " Then re-run:  ./start.sh"
        echo "════════════════════════════════════════════════════════════"
        exit 1
    else
        fail ".env and .env.example both missing. Cannot continue."
    fi
fi

# Preserve explicit CLI/provider overrides so .env does not clobber them.
CLI_LLM_PROVIDER="${LLM_PROVIDER:-}"
CLI_LLM_MODEL="${LLM_MODEL:-}"

# Load .env into this shell so we can validate required keys.
set -a
# shellcheck source=/dev/null
source .env
set +a

# Re-apply explicit CLI overrides if provided.
if [ -n "$CLI_LLM_PROVIDER" ]; then
    LLM_PROVIDER="$CLI_LLM_PROVIDER"
fi
if [ -n "$CLI_LLM_MODEL" ]; then
    LLM_MODEL="$CLI_LLM_MODEL"
fi

LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
MISSING=()

case "$LLM_PROVIDER" in
    openrouter)
        [ -z "${OPENROUTER_API_KEY:-}" ] && \
            MISSING+=("OPENROUTER_API_KEY (LLM_PROVIDER=openrouter)")
        ;;
    openai)
        [ -z "${OPENAI_API_KEY:-}" ] && \
            MISSING+=("OPENAI_API_KEY (LLM_PROVIDER=openai)")
        ;;
    anthropic)
        [ -z "${ANTHROPIC_API_KEY:-}" ] && \
            MISSING+=("ANTHROPIC_API_KEY (LLM_PROVIDER=anthropic)")
        ;;
    ollama)
        ;; # local — no key needed
    *)
        echo "[start] WARNING: LLM_PROVIDER='$LLM_PROVIDER' is not recognised." >&2
        ;;
esac

if [ "${#MISSING[@]}" -gt 0 ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo " .env is missing required values. Open .env and set:"
    for key in "${MISSING[@]}"; do
        echo "   • $key"
    done
    echo ""
    echo " Then re-run:  ./start.sh"
    echo "════════════════════════════════════════════════════════════"
    exit 1
fi

echo "[start] .env OK  (LLM_PROVIDER=$LLM_PROVIDER)"

# ── 4. Clear stale processes on target ports ────────────────────────
# If a previous start.sh was backgrounded or killed without cleanup,
# the ports may still be held. Kill any holder so bind always succeeds.
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    held=$(lsof -ti:"$port" 2>/dev/null | sort -u) || true
    if [ -n "$held" ]; then
        echo "[start] Port $port busy — clearing stale process(es): $held"
        echo "$held" | xargs kill -9 2>/dev/null || true
        sleep 0.5
    fi
done

# ── 5. Launch servers ───────────────────────────────────────────────
mkdir -p logs
BACKEND_LOG="logs/backend.log"
FRONTEND_LOG="logs/frontend.log"
FLUTTER_LOG="logs/flutter_web.log"
RUN_FLUTTER=0

_cleanup_done=0
cleanup() {
    [ "$_cleanup_done" -eq 1 ] && return
    _cleanup_done=1
    echo ""
    echo "[start] Stopping servers…"
    if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    if [ -n "${FLUTTER_PID:-}" ] && kill -0 "$FLUTTER_PID" 2>/dev/null; then
        kill "$FLUTTER_PID" 2>/dev/null || true
        wait "$FLUTTER_PID" 2>/dev/null || true
    fi
    echo "[start] Done."
}
trap cleanup INT TERM EXIT

echo "[start] Backend  → http://127.0.0.1:${BACKEND_PORT}  (log: $BACKEND_LOG)"
"$VENV_PY" -m uvicorn dischargeiq.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" --reload \
    >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "[start] Frontend → http://127.0.0.1:${FRONTEND_PORT} (log: $FRONTEND_LOG)"
# --server.headless true skips Streamlit's first-run interactive email
# prompt (which blocks forever when stdin is redirected) and stops it
# from auto-opening a browser tab.
"$VENV_PY" -m streamlit run streamlit_app.py \
    --server.address 127.0.0.1 --server.port "$FRONTEND_PORT" \
    --server.headless true --browser.gatherUsageStats false \
    >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

if command -v flutter >/dev/null 2>&1 && [ -d "dischargeiq_mobile" ]; then
    RUN_FLUTTER=1
    echo "[start] Flutter  → http://127.0.0.1:${FLUTTER_WEB_PORT} (log: $FLUTTER_LOG)"
    (
        cd "dischargeiq_mobile"
        flutter run -d chrome --web-port "$FLUTTER_WEB_PORT"
    ) >"$FLUTTER_LOG" 2>&1 &
    FLUTTER_PID=$!
else
    echo "[start] Flutter  → skipped (install Flutter and ensure ./dischargeiq_mobile exists)"
fi

echo ""
echo "[start] Services running. Press Ctrl-C to stop."
echo "[start] Open Streamlit: http://127.0.0.1:${FRONTEND_PORT}"
if [ "$RUN_FLUTTER" -eq 1 ]; then
    echo "[start] Open Flutter:  http://127.0.0.1:${FLUTTER_WEB_PORT}"
fi

# Wait until backend or Streamlit exits, or the user hits Ctrl-C.
# Flutter is NOT part of this loop: `flutter run -d chrome` often exits
# immediately when Chrome/device is missing or the project fails to build.
# If we waited on FLUTTER_PID, one failed Flutter start would tear down the
# whole stack right after "Services running."
# (Avoid `wait -n` — not available in macOS's default bash 3.2.)
while true; do
    kill -0 "$BACKEND_PID" 2>/dev/null || break
    kill -0 "$FRONTEND_PID" 2>/dev/null || break
    sleep 1
done
