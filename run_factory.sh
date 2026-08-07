#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_STATE_ROOT="${ROOT}/.var/upi_app_factory"
HOST="${UPI_APP_FACTORY_HOST:-127.0.0.1}"
PORT="${UPI_APP_FACTORY_PORT:-8036}"
STATE_ROOT="${UPI_APP_FACTORY_STATE_ROOT:-${DEFAULT_STATE_ROOT}}"
URL_FILE=""
NO_BROWSER=0
TIMEOUT="${UPI_APP_FACTORY_START_TIMEOUT_SECONDS:-30}"

usage() {
  cat <<'USAGE'
Usage: ./run_factory.sh [--no-browser] [--host 127.0.0.1|localhost] [--port PORT|0] [--state-root PATH] [--url-file PATH]

Starts the local UPI App Factory operator portal at /operator-ui/.
Default state root: ./.var/upi_app_factory
Default mode: deterministic, mock-safe, no OpenAI API key is required.
USAGE
}

fail() {
  echo "ERROR: $*" >&2
  echo "Next steps:" >&2
  echo "  - Check logs under: ${STATE_ROOT}/logs" >&2
  echo "  - Retry with an unused --port, or use --port 0 to auto-select a port." >&2
  echo "  - Keep the host loopback-only: 127.0.0.1 or localhost." >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-browser)
      NO_BROWSER=1
      shift
      ;;
    --host)
      HOST="${2:?--host requires a value}"
      shift 2
      ;;
    --port)
      PORT="${2:?--port requires a value}"
      shift 2
      ;;
    --state-root)
      STATE_ROOT="${2:?--state-root requires a value}"
      shift 2
      ;;
    --url-file)
      URL_FILE="${2:?--url-file requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "Unknown argument: $1"
      ;;
  esac
done

if [[ "${HOST}" != "127.0.0.1" && "${HOST}" != "localhost" ]]; then
  fail "Refusing non-loopback host: ${HOST}"
fi
if [[ ! "${PORT}" =~ ^[0-9]+$ ]]; then
  fail "--port must be an integer from 0 to 65535"
fi
if (( PORT > 65535 )); then
  fail "--port must be between 0 and 65535"
fi

mkdir -p \
  "${STATE_ROOT}/runs" \
  "${STATE_ROOT}/portfolio" \
  "${STATE_ROOT}/runtime" \
  "${STATE_ROOT}/logs" \
  "${STATE_ROOT}/downloads" \
  "${STATE_ROOT}/evidence"

PYTHON="${UPI_APP_FACTORY_BOOTSTRAP_PYTHON:-$(command -v python3 || true)}"
if [[ -z "${PYTHON}" ]]; then
  fail "python3 was not found on PATH"
fi

VENV_PYTHON="${ROOT}/.venv/bin/python"
REQ_FILE="${ROOT}/requirements-recipient.txt"
BOOTSTRAP_REQ_FILE="${ROOT}/requirements/bootstrap-lock.txt"
RECIPIENT_LOCK_FILE="${ROOT}/requirements/recipient-lock.txt"
PYPROJECT_FILE="${ROOT}/pyproject.toml"
REQ_STAMP="${ROOT}/.venv/.upi_app_factory_recipient_requirements.sha256"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  "${PYTHON}" -m venv "${ROOT}/.venv" || fail "Could not create .venv"
fi

REQ_HASH="$("${VENV_PYTHON}" - "${BOOTSTRAP_REQ_FILE}" "${REQ_FILE}" "${RECIPIENT_LOCK_FILE}" "${PYPROJECT_FILE}" <<'PY'
from pathlib import Path
import hashlib
import sys

digest = hashlib.sha256()
for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    digest.update(path.name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
)"

verify_locked_environment() {
  "${VENV_PYTHON}" - "${BOOTSTRAP_REQ_FILE}" "${RECIPIENT_LOCK_FILE}" <<'PY'
from importlib import metadata
from pathlib import Path
import re
import sys

def canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

expected = {}
errors = []
for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if match is None:
            errors.append(f"{path.name}: non-exact lock entry: {line}")
            continue
        name, version = match.groups()
        canonical_name = canonicalize(name)
        if canonical_name in expected:
            errors.append(f"duplicate locked distribution: {canonical_name}")
            continue
        expected[canonical_name] = version
installed = {}
for distribution in metadata.distributions():
    name = distribution.metadata.get("Name")
    if name:
        installed[canonicalize(name)] = distribution.version
allowed_first_party = {"upi-app-factory"}
missing = sorted(set(expected) - set(installed))
mismatches = sorted((name, expected[name], installed[name]) for name in set(expected).intersection(installed) if expected[name] != installed[name])
extras = sorted(set(installed) - set(expected) - allowed_first_party)
for name in missing:
    errors.append(f"{name}: locked distribution not installed")
for name, expected_version, installed_version in mismatches:
    errors.append(f"{name}: expected {expected_version}, found {installed_version}")
if extras:
    errors.append(f"unlocked installed distributions: {extras}")
print("true" if not errors else "false")
for error in errors:
    print(error, file=sys.stderr)
PY
}

LOCK_OK="false"
if [[ -f "${REQ_STAMP}" ]]; then
  LOCK_OK="$(verify_locked_environment)"
fi

if [[ ! -f "${REQ_STAMP}" || "$(tr -d '[:space:]' < "${REQ_STAMP}")" != "${REQ_HASH}" || "${LOCK_OK}" != "true" ]]; then
  "${VENV_PYTHON}" -m pip install -r "${BOOTSTRAP_REQ_FILE}" || fail "Bootstrap dependency install failed"
  "${VENV_PYTHON}" -m pip install -r "${REQ_FILE}" || fail "Dependency install failed from requirements-recipient.txt"
  LOCK_OK="$(verify_locked_environment)"
  [[ "${LOCK_OK}" == "true" ]] || fail "Recipient dependency lock verification failed after install"
  printf '%s\n' "${REQ_HASH}" > "${REQ_STAMP}"
fi

"${VENV_PYTHON}" -m pip check || fail "Recipient dependency consistency check failed"

"${VENV_PYTHON}" - <<'PY' || fail "Recipient runtime verification failed; install from requirements-recipient.txt"
import fastapi
import uvicorn
import pydantic
PY

export UPI_APP_FACTORY_PYTHON="${VENV_PYTHON}"
export REAL_PAYMENT_CALLS=disabled
export FACTORY_LLM_ENABLED=0
export UPI_APP_FACTORY_STATE_ROOT="${STATE_ROOT}"
export UPI_APP_FACTORY_HOST="${HOST}"
export UPI_APP_FACTORY_PORT="${PORT}"
export UPI_APP_FACTORY_START_TIMEOUT_SECONDS="${TIMEOUT}"

START_OUTPUT="$("${ROOT}/start_factory.sh" --host "${HOST}" --port "${PORT}" --state-root "${STATE_ROOT}" 2>&1)" || {
  echo "${START_OUTPUT}" >&2
  fail "Operator portal did not start"
}

URL="$(printf '%s\n' "${START_OUTPUT}" | sed -n 's/^URL=//p' | tail -n 1)"
if [[ -z "${URL}" ]]; then
  fail "Launcher did not report an operator URL"
fi

if [[ -n "${URL_FILE}" ]]; then
  mkdir -p "$(dirname -- "${URL_FILE}")"
  printf '%s\n' "${URL}" > "${URL_FILE}"
fi

if [[ "${NO_BROWSER}" -eq 0 ]]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${URL}" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "${URL}" >/dev/null 2>&1 || true
  fi
fi

printf '%s\n' "${URL}"
