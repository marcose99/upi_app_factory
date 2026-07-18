from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from upi_factory.rubric_alignment.utils import project_root, sha256_file, write_json


INCLUDE_PATHS = [
    "docs/capstone/phase66",
    "src/upi_factory/rubric_alignment",
    "tests/test_phase66_rubric_alignment.py",
    "tests/fixtures/phase66",
    "scripts/run_phase66_offline_evaluation.py",
    "scripts/run_phase66_live_openai_evaluation.py",
    "scripts/validate_phase66_rubric_alignment.py",
    "scripts/build_phase66_evaluator_handoff.py",
    "requirements/phase66-ai-eval.txt",
    "workspace/phase66_rubric_alignment/offline",
    "evidence/phase66/live",
]


def build_handoff(output_dir: Path) -> dict[str, Any]:
    root = project_root()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    copied: list[str] = []
    for rel in INCLUDE_PATHS:
        source = root / rel
        if not source.exists():
            continue
        destination = output_dir / rel
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
            copied.extend(path.relative_to(output_dir).as_posix() for path in destination.rglob("*") if path.is_file())
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(destination.relative_to(output_dir).as_posix())
    manifest = {
        "product_id": "upi_app_factory",
        "product_name": "UPI App Factory",
        "app_id": "upi_dispute_resolution",
        "commit": commit,
        "commands": [
            "python scripts/run_phase66_offline_evaluation.py --output-root workspace/phase66_rubric_alignment/offline",
            "python scripts/run_phase66_live_openai_evaluation.py --approve-live-openai-evaluation --output-root evidence/phase66/live --llm-model gpt-5.6-luna --embedding-model text-embedding-3-small --max-llm-calls 45",
            "python scripts/validate_phase66_rubric_alignment.py",
            "python scripts/validate_phase66_rubric_alignment.py --require-live-evidence",
        ],
        "environment_assumptions": ["Python 3.10+", "offline tests require no credentials or network", "live evaluation requires explicit flag and OPENAI_API_KEY"],
        "limitations": ["No production payment integrations", "No certification or production-readiness claim", "Measured live fields remain NOT_RUN until guarded live execution"],
        "files": [{"path": rel, "sha256": sha256_file(output_dir / rel)} for rel in sorted(copied)],
    }
    write_json(output_dir / "phase66_handoff_manifest.json", manifest)
    return manifest
