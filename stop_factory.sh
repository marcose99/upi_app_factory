#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STATE_BASE="${UPI_APP_FACTORY_STATE_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/upi_app_factory/operator_portal}"
PID_FILE="${STATE_BASE}/operator_portal.pid"
TIMEOUT="${UPI_APP_FACTORY_STOP_TIMEOUT_SECONDS:-10}"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "Operator portal is not running"
  exit 0
fi

PID="$(tr -d '[:space:]' < "${PID_FILE}")"
if [[ ! "${PID}" =~ ^[0-9]+$ ]] || ! kill -0 "${PID}" 2>/dev/null; then
  rm -f "${PID_FILE}"
  echo "Operator portal is not running"
  exit 0
fi

CMDLINE="$(tr '\0' ' ' < "/proc/${PID}/cmdline" 2>/dev/null || true)"
if [[ "${CMDLINE}" != *"${ROOT}/scripts/run_phase36_operator_portal_local_web_ui.py"* ]]; then
  echo "Refusing to stop PID ${PID}: process does not match this repository portal command" >&2
  exit 3
fi

kill -INT "${PID}"
deadline=$((SECONDS + TIMEOUT))
while kill -0 "${PID}" 2>/dev/null; do
  if (( SECONDS >= deadline )); then
    kill -TERM "${PID}"
    break
  fi
  sleep 0.2
done

while kill -0 "${PID}" 2>/dev/null; do
  sleep 0.2
done
rm -f "${PID_FILE}"
echo "Operator portal stopped"
