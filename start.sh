#!/usr/bin/env bash
# AUTOGEN-compatible start script for RUN platform API deployment.
set -euo pipefail

PORT="${PORT:-8000}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/run-app.log"
PID_FILE="/tmp/run-app.pid"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  old_pid="$(cat "${PID_FILE}")"
  echo "[run-app] restarting existing pid=${old_pid}"
  kill "${old_pid}" 2>/dev/null || true
  sleep 2
  if kill -0 "${old_pid}" 2>/dev/null; then
    kill -9 "${old_pid}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"
fi

cd "${APP_DIR}"
nohup bash -lc 'pip install -r requirements.txt && python3 main.py' > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"
sleep 1
if kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "[run-app] started ok pid=$(cat "${PID_FILE}") port=${PORT}"
else
  echo "[run-app] FAILED to start"
  tail -n 50 "${LOG_FILE}" || true
  exit 1
fi
