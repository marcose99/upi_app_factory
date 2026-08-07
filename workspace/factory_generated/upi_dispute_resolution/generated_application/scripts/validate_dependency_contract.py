#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_exact_lock(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if match is None:
            raise AssertionError(f"{path.name}: non-exact requirement: {line}")
        name, version = match.groups()
        key = canonical_name(name)
        if key in result:
            raise AssertionError(f"{path.name}: duplicate distribution: {key}")
        result[key] = version
    if not result:
        raise AssertionError(f"{path.name}: empty lock")
    return result


def load_contract() -> dict[str, Any]:
    payload = json.loads((ROOT / "dependency_contract.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("dependency_contract.json must contain an object")
    return payload


def main() -> int:
    contract = load_contract()
    bootstrap = parse_exact_lock(ROOT / "requirements-bootstrap.lock")
    locked = parse_exact_lock(ROOT / "requirements.lock")

    assert sha256_file(ROOT / "requirements-bootstrap.lock") == contract[
        "bootstrap_lock_sha256"
    ]
    assert sha256_file(ROOT / "requirements.lock") == contract[
        "requirements_lock_sha256"
    ]

    direct = {
        canonical_name(str(name))
        for name in contract["direct_distributions"]
    }
    assert direct.issubset(locked), sorted(direct - set(locked))
    assert int(bootstrap["setuptools"].split(".", 1)[0]) >= 83

    start_script = (ROOT / "scripts/start_local.sh").read_text(encoding="utf-8")
    assert '${APP_ROOT}/.venv/bin/python' in start_script

    bootstrap_script = (ROOT / "scripts/bootstrap_cleanroom.sh").read_text(
        encoding="utf-8"
    )
    for marker in (
        "requirements-bootstrap.lock",
        "requirements.lock",
        "pip check",
        "validate_dependency_contract.py",
    ):
        assert marker in bootstrap_script

    print(
        json.dumps(
            {
                "status": "PASS",
                "direct_distribution_count": len(direct),
                "locked_distribution_count": len(locked),
                "bootstrap_distribution_count": len(bootstrap),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
