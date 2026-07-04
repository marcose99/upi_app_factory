#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/marcose/projects/upi_dispute_resolution_factory}"

cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python -m factory.validators.validate_baseline_provenance
