#!/usr/bin/env bash
# Cloud Run entrypoint — multiplexes FastAPI + Streamlit behind nginx.
#   - FastAPI (uvicorn)  -> 127.0.0.1:${BACKEND_PORT}    (loopback only)
#   - Streamlit          -> 127.0.0.1:${STREAMLIT_PORT}  (loopback only)
#   - nginx              -> 0.0.0.0:${PORT}              (Cloud Run public)
# Browser hits same-origin /api/* -> FastAPI, everything else -> Streamlit.
set -euo pipefail

PORT="${PORT:-8080}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

echo "[entrypoint] Starting FastAPI on 127.0.0.1:${BACKEND_PORT}"
python -m uvicorn dischargeiq.main:app \
    --host 127.0.0.1 --port "${BACKEND_PORT}" \
    --workers 1 --log-level info &
BACKEND_PID=$!

# Wait for FastAPI's /health to return 200 before starting Streamlit / nginx.
for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
        echo "[entrypoint] FastAPI healthy"
        break
    fi
    sleep 0.5
done

echo "[entrypoint] Starting Streamlit on 127.0.0.1:${STREAMLIT_PORT}"
python -m streamlit run streamlit_app.py \
    --server.address 127.0.0.1 \
    --server.port "${STREAMLIT_PORT}" \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false &
STREAMLIT_PID=$!

# Render nginx config from template (substitutes $PORT etc.).
export PORT BACKEND_PORT STREAMLIT_PORT
envsubst '${PORT} ${BACKEND_PORT} ${STREAMLIT_PORT}' \
    < /app/nginx.conf.template > /etc/nginx/nginx.conf

# Wait briefly for Streamlit to start serving.
for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${STREAMLIT_PORT}/_stcore/health" >/dev/null 2>&1; then
        echo "[entrypoint] Streamlit healthy"
        break
    fi
    sleep 0.5
done

cleanup() {
    kill "${BACKEND_PID}" 2>/dev/null || true
    kill "${STREAMLIT_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[entrypoint] Starting nginx on 0.0.0.0:${PORT}"
exec nginx -g 'daemon off;'
