#!/usr/bin/env bash
# DischargeIQ — one-command startup for macOS / Linux.
#
# What this does:
#   1. Creates .venv if missing and installs requirements.txt.
#   2. Verifies .env exists and that required API keys are non-empty.
#      Exits with clear instructions if any required key is missing.
#   3. Starts the FastAPI backend (uvicorn) on http://127.0.0.1:8000.
#   4. Starts the Streamlit frontend on http://127.0.0.1:8501.
#   5. Ctrl-C stops both cleanly.

set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
VENV_DIR=".venv"
BACKEND_PORT=8000
FRONTEND_PORT=8501

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

echo "[start] Installing requirements (quiet)"
pip install --quiet --disable-pip-version-check -r requirements.txt

# ── 3. .env validation ──────────────────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo ""
        echo "════════════════════════════════════════════════════════════"
        echo " .env created from .env.example."
        echo ""
        echo " ACTION REQUIRED — edit .env and fill in at minimum:"
        echo "   • ANTHROPIC_API_KEY   (Claude — used by Agents 2-5)"
        echo ""
        echo " Depending on LLM_PROVIDER, also set ONE of:"
        echo "   • OPENROUTER_API_KEY  (if LLM_PROVIDER=openrouter, default)"
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

# Load .env into this shell so we can validate required keys.
set -a
# shellcheck source=/dev/null
source .env
set +a

LLM_PROVIDER="${LLM_PROVIDER:-openrouter}"
MISSING=()

[ -z "${ANTHROPIC_API_KEY:-}" ] && MISSING+=("ANTHROPIC_API_KEY (Claude — Agents 2-5)")

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
        ;; # ANTHROPIC_API_KEY already checked above
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

# ── 4. Launch servers ───────────────────────────────────────────────
mkdir -p logs
BACKEND_LOG="logs/backend.log"
FRONTEND_LOG="logs/frontend.log"

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
    echo "[start] Done."
}
trap cleanup INT TERM EXIT

echo "[start] Backend  → http://127.0.0.1:${BACKEND_PORT}  (log: $BACKEND_LOG)"
uvicorn dischargeiq.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" --reload \
    >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "[start] Frontend → http://127.0.0.1:${FRONTEND_PORT} (log: $FRONTEND_LOG)"
# --server.headless true skips Streamlit's first-run interactive email
# prompt (which blocks forever when stdin is redirected) and stops it
# from auto-opening a browser tab.
streamlit run streamlit_app.py \
    --server.address 127.0.0.1 --server.port "$FRONTEND_PORT" \
    --server.headless true --browser.gatherUsageStats false \
    >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo ""
echo "[start] Both servers running. Press Ctrl-C to stop."
echo "[start] Open: http://127.0.0.1:${FRONTEND_PORT}"

# Wait until either child exits or the user hits Ctrl-C.
# (Avoid `wait -n` — not available in macOS's default bash 3.2.)
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done
