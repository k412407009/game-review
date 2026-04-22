#!/usr/bin/env bash
# AUTOGEN by run-platform-deploy skill. 可手工编辑.
set -euo pipefail
PORT="${PORT:-8000}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/run-app.log"
PID_FILE="/tmp/run-app.pid"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "[run-app] already running, pid=$(cat "${PID_FILE}")"; exit 0
fi
cd "${APP_DIR}"
nohup bash -lc 'true && python3 main.py' > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"
sleep 1
if kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "[run-app] started ok pid=$(cat "${PID_FILE}") port=${PORT}"
else
  echo "[run-app] FAILED to start"; tail -n 50 "${LOG_FILE}" || true; exit 1
fi
