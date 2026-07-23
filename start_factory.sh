#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOST="${UPI_APP_FACTORY_HOST:-127.0.0.1}"
PORT="${UPI_APP_FACTORY_PORT:-8036}"
STATE_BASE="${UPI_APP_FACTORY_STATE_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/upi_app_factory/operator_portal}"
LOG_LEVEL="${UPI_APP_FACTORY_LOG_LEVEL:-INFO}"
PID_FILE="${STATE_BASE}/operator_portal.pid"
LOG_FILE="${STATE_BASE}/operator_portal.jsonl"

if [[ "${HOST}" != "127.0.0.1" && "${HOST}" != "localhost" ]]; then
  echo "Refusing non-loopback host: ${HOST}" >&2
  exit 2
fi

mkdir -p "${STATE_BASE}"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(tr -d '[:space:]' < "${PID_FILE}")"
  if [[ "${OLD_PID}" =~ ^[0-9]+$ ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "Operator portal already running"
    echo "URL=http://${HOST}:${PORT}/operator-ui/"
    echo "PID=${OLD_PID}"
    echo "PID_FILE=${PID_FILE}"
    echo "LOG_FILE=${LOG_FILE}"
    exit 0
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

nohup "${PYTHON}" "${ROOT}/scripts/run_phase36_operator_portal_local_web_ui.py" \
  --host "${HOST}" \
  --port "${PORT}" \
  --portfolio-state-root "${STATE_BASE}/portfolio" \
  >>"${LOG_FILE}" 2>&1 &
PID="$!"
printf '%s\n' "${PID}" > "${PID_FILE}"

echo "Operator portal started"
echo "URL=http://${HOST}:${PORT}/operator-ui/"
echo "PID=${PID}"
echo "PID_FILE=${PID_FILE}"
echo "LOG_FILE=${LOG_FILE}"
