#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-$(command -v python3.10 || command -v python3 || true)}"
VENV="${APP_ROOT}/.venv"
[[ -n "${PYTHON_BOOTSTRAP}" ]] || { printf 'ERROR: Python 3.10+ not found\n' >&2; exit 2; }
"${PYTHON_BOOTSTRAP}" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3,10) else "Python 3.10+ required")
PY
[[ -x "${VENV}/bin/python" ]] || "${PYTHON_BOOTSTRAP}" -m venv "${VENV}"
"${VENV}/bin/python" -m pip install --disable-pip-version-check -r "${APP_ROOT}/requirements-bootstrap.lock"
"${VENV}/bin/python" -m pip install --disable-pip-version-check -r "${APP_ROOT}/requirements.lock"
"${VENV}/bin/python" -m pip check
"${VENV}/bin/python" - "${APP_ROOT}/requirements-bootstrap.lock" "${APP_ROOT}/requirements.lock" <<'PY'
from importlib import metadata
from pathlib import Path
import re
import sys

def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

expected = {}
for raw_path in sys.argv[1:]:
    for raw in Path(raw_path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if match is None:
            raise SystemExit(f"non-exact lock entry: {line}")
        expected[canon(match.group(1))] = match.group(2)
installed = {}
for dist in metadata.distributions():
    name = dist.metadata.get("Name")
    if name:
        installed[canon(name)] = dist.version
missing = sorted(set(expected) - set(installed))
mismatch = sorted((n, expected[n], installed.get(n)) for n in expected if installed.get(n) != expected[n])
extras = sorted(set(installed) - set(expected))
if missing or mismatch or extras:
    raise SystemExit(f"dependency closure mismatch: missing={missing} mismatch={mismatch} extras={extras}")
print(f"GENERATED_APP_EXACT_INSTALLED_CLOSURE=PASS count={len(expected)}")
PY
"${VENV}/bin/python" "${APP_ROOT}/scripts/validate_dependency_contract.py"
printf 'GENERATED_APP_BOOTSTRAP_STATUS=PASS\n'
printf 'GENERATED_APP_PYTHON=%s\n' "${VENV}/bin/python"
