from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upi_factory.rubric_alignment.live import require_live_gate
from upi_factory.rubric_alignment.models import Phase66Error
from upi_factory.rubric_alignment.prompts import prompt_variants
from upi_factory.rubric_alignment.utils import project_root, sha256_file


REQUIRED_PATHS = [
    "docs/capstone/phase66/problem_framing.md",
    "docs/capstone/phase66/rubric_evidence_matrix.md",
    "docs/capstone/phase66/architecture.md",
    "docs/capstone/phase66/phase66_evaluation_summary.md",
    "scripts/run_phase66_offline_evaluation.py",
    "scripts/run_phase66_live_openai_evaluation.py",
    "scripts/validate_phase66_rubric_alignment.py",
    "scripts/build_phase66_evaluator_handoff.py",
    "src/upi_factory/rubric_alignment/__init__.py",
]


def validate_manifest(manifest_path: Path, *, root: Path | None = None) -> None:
    base = root or manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest.get("files", []):
        path = base / str(item["path"])
        if not path.exists():
            raise Phase66Error(f"manifest tamper failure: missing {item['path']}")
        if sha256_file(path) != item["sha256"]:
            raise Phase66Error(f"manifest tamper failure: changed {item['path']}")


def validate_phase66(*, require_live_evidence: bool = False) -> dict[str, Any]:
    root = project_root()
    missing = [path for path in REQUIRED_PATHS if not (root / path).exists()]
    if missing:
        raise Phase66Error(f"missing required Phase 66 paths: {missing}")
    if len(prompt_variants()) != 3:
        raise Phase66Error("expected exactly three prompt variants")
    if require_live_evidence:
        live_manifest = root / "evidence" / "phase66" / "live" / "manifest.json"
        if not live_manifest.exists():
            raise Phase66Error("live evidence required but evidence/phase66/live/manifest.json is absent")
        require_live_gate(approved=True)
    offline_manifest = root / "workspace" / "phase66_rubric_alignment" / "offline" / "manifest.json"
    if offline_manifest.exists():
        validate_manifest(offline_manifest)
    return {"passed": True, "require_live_evidence": require_live_evidence, "checked_paths": REQUIRED_PATHS}
