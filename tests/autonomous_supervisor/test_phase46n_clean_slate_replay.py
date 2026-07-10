from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.autonomous_supervisor.clean_slate import (
    copy_prerequisites,
    discover_generation_command,
    remove_generated_outputs,
)


def test_copy_prerequisites_verifies_hashes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    relative = "workspace/evidence.json"
    path = source / relative
    path.parent.mkdir(parents=True)
    path.write_text('{"status": "PASSED"}\n', encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": [
                    {"path": relative, "sha256": digest}
                ]
            }
        ),
        encoding="utf-8",
    )
    records = copy_prerequisites(
        source,
        target,
        manifest,
    )
    assert records[0]["sha256"] == digest
    assert (target / relative).is_file()


def test_remove_generated_outputs_is_sandbox_scoped(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    target = (
        root
        / "workspace/factory_generated/upi_dispute_resolution"
        / "generated_app"
    )
    target.mkdir(parents=True)
    (target / "file.txt").write_text("data", encoding="utf-8")
    removed = remove_generated_outputs(root)
    assert (
        "workspace/factory_generated/upi_dispute_resolution/"
        "generated_app"
    ) in removed
    assert not target.exists()


def test_generation_command_prefers_phase30(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    script = (
        root
        / "scripts/run_phase30_deep_generated_application_regeneration.py"
    )
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    command = discover_generation_command(
        root,
        Path("/usr/bin/python3"),
    )
    assert command[-1].endswith(
        "run_phase30_deep_generated_application_regeneration.py"
    )
