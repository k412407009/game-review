#!/usr/bin/env bash
# AUTOGEN by run-platform-deploy skill. 可手工编辑.
set -euo pipefail
PORT="${PORT:-3000}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/run-app.log"
PID_FILE="/tmp/run-app.pid"
BOOTSTRAP_LOCK_DIR="/tmp/game-review-web-bootstrap.lock"

kill_port_users() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:"${PORT}" | xargs -r kill 2>/dev/null || true
    sleep 1
    lsof -ti tcp:"${PORT}" | xargs -r kill -9 2>/dev/null || true
    return
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}"/tcp 2>/dev/null || true
    sleep 1
    fuser -k -9 "${PORT}"/tcp 2>/dev/null || true
    return
  fi
  pkill -f 'next start --hostname 0.0.0.0 --port 3000' 2>/dev/null || true
  pkill -f 'next-server' 2>/dev/null || true
}

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

kill_port_users

cd "${APP_DIR}"
nohup env PORT="${PORT}" APP_DIR="${APP_DIR}" BOOTSTRAP_LOCK_DIR="${BOOTSTRAP_LOCK_DIR}" bash -lc '
set -euo pipefail

acquire_bootstrap_lock() {
  local tries=0
  until mkdir "${BOOTSTRAP_LOCK_DIR}" 2>/dev/null; do
    tries=$((tries + 1))
    if [[ ${tries} -ge 120 ]]; then
      echo "[run-app] bootstrap lock timeout"
      return 1
    fi
    sleep 1
  done
}

release_bootstrap_lock() {
  rmdir "${BOOTSTRAP_LOCK_DIR}" 2>/dev/null || true
}

cd "${APP_DIR}"
acquire_bootstrap_lock
trap release_bootstrap_lock EXIT

if [[ ! -d node_modules ]]; then
  echo "[run-app] installing node dependencies"
  if [[ -f package-lock.json ]]; then
    npm ci --include=dev
  else
    npm install --production=false
  fi
fi

if [[ ! -f .next/BUILD_ID ]]; then
  echo "[run-app] building next app"
  npm run build
fi

release_bootstrap_lock
trap - EXIT

exec ./node_modules/.bin/next start --hostname 0.0.0.0 --port "${PORT}"
' > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"
sleep 1
if kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "[run-app] started ok pid=$(cat "${PID_FILE}") port=${PORT}"
else
  echo "[run-app] FAILED to start"; tail -n 50 "${LOG_FILE}" || true; exit 1
fi
