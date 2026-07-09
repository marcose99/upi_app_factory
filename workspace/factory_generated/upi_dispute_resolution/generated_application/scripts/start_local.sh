#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${APP_ROOT}/../../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"
HOST="${UPI_DISPUTE_LOCAL_HOST:-127.0.0.1}"
PORT="${UPI_DISPUTE_LOCAL_PORT:-8042}"

export PYTHONPATH="${APP_ROOT}/app${PYTHONPATH:+:${PYTHONPATH}}"
export UPI_DISPUTE_APP_ENV="${UPI_DISPUTE_APP_ENV:-local}"
export UPI_DISPUTE_DATA_DIR="${UPI_DISPUTE_DATA_DIR:-var/local_runtime}"
export UPI_DISPUTE_SQLITE_PATH="${UPI_DISPUTE_SQLITE_PATH:-var/local_runtime/disputes.sqlite3}"
export UPI_DISPUTE_AUDIT_LOG_PATH="${UPI_DISPUTE_AUDIT_LOG_PATH:-var/local_runtime/audit_events.jsonl}"
export UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE="${UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE:-mock}"
export UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS="${UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS:-false}"
export UPI_DISPUTE_ALLOW_REAL_SECRETS="${UPI_DISPUTE_ALLOW_REAL_SECRETS:-false}"

cd "${APP_ROOT}"
mkdir -p "${UPI_DISPUTE_DATA_DIR}"

exec "${PYTHON_BIN}" -m uvicorn upi_dispute_app.main:app --host "${HOST}" --port "${PORT}"
