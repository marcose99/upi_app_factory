#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/marcose/projects/upi_dispute_resolution_factory}"
RUN_ID="${RUN_ID:-manual_$(date -u +%Y%m%dT%H%M%SZ)}"

cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python -m factory.generators.mock_dispute_app_generator \
  --run-id "$RUN_ID" \
  --clean
