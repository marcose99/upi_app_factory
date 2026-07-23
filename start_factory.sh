#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOST="${UPI_APP_FACTORY_HOST:-127.0.0.1}"
PORT="${UPI_APP_FACTORY_PORT:-8036}"
STATE_BASE="${UPI_APP_FACTORY_STATE_ROOT:-${ROOT}/.var/upi_app_factory}"
LOG_LEVEL="${UPI_APP_FACTORY_LOG_LEVEL:-INFO}"
TIMEOUT="${UPI_APP_FACTORY_START_TIMEOUT_SECONDS:-30}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:?--host requires a value}"
      shift 2
      ;;
    --port)
      PORT="${2:?--port requires a value}"
      shift 2
      ;;
    --state-root)
      STATE_BASE="${2:?--state-root requires a value}"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./start_factory.sh [--host 127.0.0.1|localhost] [--port PORT|0] [--state-root PATH]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

PID_FILE="${STATE_BASE}/runtime/operator_portal.pid"
PORT_FILE="${STATE_BASE}/runtime/operator_portal.port"
LOG_FILE="${STATE_BASE}/logs/operator_portal.jsonl"

if [[ "${HOST}" != "127.0.0.1" && "${HOST}" != "localhost" ]]; then
  echo "Refusing non-loopback host: ${HOST}" >&2
  exit 2
fi
if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || (( PORT > 65535 )); then
  echo "Port must be an integer from 0 to 65535" >&2
  exit 2
fi

mkdir -p "${STATE_BASE}/runs" "${STATE_BASE}/portfolio" "${STATE_BASE}/runtime" "${STATE_BASE}/logs" "${STATE_BASE}/downloads" "${STATE_BASE}/evidence"

allocate_port() {
  "${PYTHON:-python3}" - "$HOST" <<'PY'
import socket
import sys
host = sys.argv[1]
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind((host, 0))
    print(sock.getsockname()[1])
PY
}

port_is_available() {
  "${PYTHON:-python3}" - "$HOST" "$1" <<'PY'
import socket
import sys
host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    try:
        sock.bind((host, port))
    except OSError:
        raise SystemExit(1)
PY
}

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(tr -d '[:space:]' < "${PID_FILE}")"
  if [[ "${OLD_PID}" =~ ^[0-9]+$ ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    CMDLINE="$(tr '\0' ' ' < "/proc/${OLD_PID}/cmdline" 2>/dev/null || true)"
    if [[ "${CMDLINE}" != *"${ROOT}/scripts/run_phase36_operator_portal_local_web_ui.py"* ]]; then
      rm -f "${PID_FILE}" "${PORT_FILE}"
      echo "Removed stale PID file for PID ${OLD_PID}; process did not match this repository portal." >&2
    else
      RUNNING_PORT="${PORT}"
      if [[ -f "${PORT_FILE}" ]]; then
        RUNNING_PORT="$(tr -d '[:space:]' < "${PORT_FILE}")"
      fi
      if "${PYTHON:-python3}" - "$HOST" "$RUNNING_PORT" <<'PY'
import json
import sys
import urllib.request
host = sys.argv[1]
port = sys.argv[2]
try:
    with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if payload.get("status") == "ok" else 1)
PY
      then
    echo "Operator portal already running"
    echo "URL=http://${HOST}:${RUNNING_PORT}/operator-ui/"
    echo "PID=${OLD_PID}"
    echo "PID_FILE=${PID_FILE}"
    echo "LOG_FILE=${LOG_FILE}"
    exit 0
      fi
      echo "PID ${OLD_PID} exists but /health is not ready; remove ${PID_FILE} or run stop_factory.sh --state-root ${STATE_BASE}" >&2
      exit 5
    fi
  else
    rm -f "${PID_FILE}" "${PORT_FILE}"
  fi
fi

PYTHON_CANDIDATES=()
if [[ -n "${UPI_APP_FACTORY_PYTHON:-}" ]]; then
  PYTHON_CANDIDATES+=("${UPI_APP_FACTORY_PYTHON}")
fi
PYTHON_CANDIDATES+=("${ROOT}/.venv/bin/python")
if [[ -r "/proc/${PPID}/cmdline" ]]; then
  PARENT_PYTHON="$(tr '\0' '\n' < "/proc/${PPID}/cmdline" | sed -n '1p')"
  if [[ -n "${PARENT_PYTHON}" ]]; then
    PYTHON_CANDIDATES+=("${PARENT_PYTHON}")
  fi
fi
PYTHON_CANDIDATES+=("$(command -v python3 || true)" "$(command -v python || true)")

PYTHON=""
for candidate in "${PYTHON_CANDIDATES[@]}"; do
  if [[ -n "${candidate}" && -x "${candidate}" ]] && "${candidate}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    PYTHON="${candidate}"
    break
  fi
done

export REAL_PAYMENT_CALLS=disabled
export FACTORY_LLM_ENABLED=0
export UPI_APP_FACTORY_LOG_LEVEL="${LOG_LEVEL}"
export UPI_APP_FACTORY_LOG_FILE="${LOG_FILE}"
export UPI_APP_FACTORY_STATE_ROOT="${STATE_BASE}"

if [[ -z "${PYTHON}" ]]; then
  echo "Operator portal requires the repository FastAPI/uvicorn runtime; install project dependencies before starting." >&2
  exit 4
fi

if [[ "${PORT}" == "0" ]]; then
  if ! PORT="$(allocate_port 2>/dev/null)"; then
    echo "Could not allocate an ephemeral loopback port. Retry with an explicit unused --port." >&2
    exit 6
  fi
elif ! port_is_available "${PORT}"; then
  echo "Port ${PORT} is already in use on ${HOST}. Retry with --port 0 or choose another port." >&2
  exit 6
fi

nohup "${PYTHON}" "${ROOT}/scripts/run_phase36_operator_portal_local_web_ui.py" \
  --host "${HOST}" \
  --port "${PORT}" \
  --browser-state-root "${STATE_BASE}/runs" \
  --runtime-state-root "${STATE_BASE}/runtime" \
  --portfolio-state-root "${STATE_BASE}/portfolio" \
  >>"${LOG_FILE}" 2>&1 &
PID="$!"
printf '%s\n' "${PID}" > "${PID_FILE}"
printf '%s\n' "${PORT}" > "${PORT_FILE}"

last_health="not checked"
deadline=$((SECONDS + TIMEOUT))
while true; do
  if ! kill -0 "${PID}" 2>/dev/null; then
    rm -f "${PID_FILE}" "${PORT_FILE}"
    echo "Operator portal process exited before becoming healthy. See ${LOG_FILE}" >&2
    tail -n 20 "${LOG_FILE}" >&2 || true
    exit 7
  fi
  if last_health="$("${PYTHON}" - "$HOST" "$PORT" <<'PY' 2>&1
import json
import sys
import urllib.request
host = sys.argv[1]
port = sys.argv[2]
with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
if payload.get("status") != "ok":
    raise SystemExit(f"unexpected health payload: {payload!r}")
print("ok")
PY
  )"; then
    break
  fi
  if (( SECONDS >= deadline )); then
    kill -TERM "${PID}" 2>/dev/null || true
    rm -f "${PID_FILE}" "${PORT_FILE}"
    echo "Operator portal did not pass /health within ${TIMEOUT}s. Last health error: ${last_health}" >&2
    echo "Log file: ${LOG_FILE}" >&2
    tail -n 20 "${LOG_FILE}" >&2 || true
    exit 8
  fi
  sleep 0.2
done

echo "Operator portal started"
echo "URL=http://${HOST}:${PORT}/operator-ui/"
echo "PID=${PID}"
echo "PID_FILE=${PID_FILE}"
echo "LOG_FILE=${LOG_FILE}"
