#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

rm -rf "${APP_ROOT}/var/local_runtime"
rm -rf "${APP_ROOT}/.pytest_cache"
find "${APP_ROOT}" -type d -name __pycache__ -prune -exec rm -rf {} +

echo "Removed known generated app local runtime artifacts."
