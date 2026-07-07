from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_phase24_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase24_multi_domain_factory_template_readiness.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase24_runner_emits_temp_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    template = tmp_path / "template.json"
    adapter = tmp_path / "adapter.json"
    gap = tmp_path / "gap.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase24_multi_domain_factory_template_readiness.py",
            "--execute-readonly-gates",
            "--audit-out",
            str(audit),
            "--template-out",
            str(template),
            "--adapter-out",
            str(adapter),
            "--gap-out",
            str(gap),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = load_json(audit)
    assert payload["status"] == "MULTI_DOMAIN_FACTORY_TEMPLATE_READY"
    assert payload["cross_domain_application_generated"] is False
