from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.lifecycle_orchestrator.engine as engine_module
from tools.lifecycle_orchestrator.engine import (
    LifecycleEngine,
    LifecycleError,
    atomic_write_text_validated,
    manifest_digest,
    numbered_checkpoint_files,
    parse_validation_metrics,
    validate_manifest,
)
from tools.lifecycle_orchestrator.models import ApprovalSet


def active_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ACTIVE",
        "phase": "99A",
        "name": "Lifecycle test",
        "base_branch": "main",
        "feature_branch": "phase99a/lifecycle-test",
        "commit_message": "test: lifecycle",
        "protected_actions": ["commit", "merge", "push"],
        "candidate_paths": ["generated/example.txt"],
        "implementation_commands": [
            {
                "name": "Implement",
                "argv": ["{python}", "-c", "print('implement')"],
            }
        ],
        "targeted_validation_commands": [
            {
                "name": "Targeted",
                "argv": ["{python}", "-m", "pytest", "-q"],
            }
        ],
        "post_restore_validation_commands": [],
        "full_validation_commands": [
            {
                "name": "Full",
                "argv": ["{python}", "-m", "pytest", "-q"],
            }
        ],
        "runtime_noise_paths": [],
        "llm": {"enabled": False, "allowed_calls": 0},
    }


def test_manifest_validation_accepts_argv_commands() -> None:
    manifest = active_manifest()
    assert validate_manifest(manifest)["phase"] == "99A"


def test_manifest_validation_rejects_draft() -> None:
    manifest = active_manifest()
    manifest["status"] = "DRAFT"
    with pytest.raises(LifecycleError, match="must be ACTIVE"):
        validate_manifest(manifest)


def test_manifest_validation_rejects_shell_operators() -> None:
    manifest = active_manifest()
    commands = manifest["implementation_commands"]
    assert isinstance(commands, list)
    command = commands[0]
    assert isinstance(command, dict)
    command["argv"] = ["python", "-c", "print(1)", "&&", "rm"]
    with pytest.raises(LifecycleError, match="Shell control"):
        validate_manifest(manifest)


def test_manifest_validation_rejects_llm_enablement() -> None:
    manifest = active_manifest()
    manifest["llm"] = {"enabled": True, "allowed_calls": 1}
    with pytest.raises(LifecycleError, match="zero LLM"):
        validate_manifest(manifest)


def test_manifest_digest_is_order_independent() -> None:
    manifest = active_manifest()
    reordered = dict(reversed(list(manifest.items())))
    assert manifest_digest(manifest) == manifest_digest(reordered)


def test_dynamic_validation_metrics_observe_growth() -> None:
    metrics = parse_validation_metrics(
        (
            "All checks passed!\n"
            "Success: no issues found in 600 source files\n"
            "900 passed in 50.00s\n"
        ),
        "",
    )
    assert metrics == {
        "mypy_source_files": 600,
        "pytest_passed": 900,
        "ruff": "PASSED",
    }


def test_dynamic_validation_metrics_do_not_require_count() -> None:
    metrics = parse_validation_metrics("command completed successfully", "")
    assert metrics == {}


def test_numbered_checkpoint_selector_ignores_summary(
    tmp_path: Path,
) -> None:
    for name in (
        "checkpoint_001.json",
        "checkpoint_002.json",
        "checkpoint_verification.json",
        "checkpoint_12.json",
    ):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    assert [
        path.name for path in numbered_checkpoint_files(tmp_path)
    ] == [
        "checkpoint_001.json",
        "checkpoint_002.json",
    ]


def test_atomic_write_validates_before_replacement(
    tmp_path: Path,
) -> None:
    target = tmp_path / "module.py"
    target.write_text("value = 1\n", encoding="utf-8")

    def validator(content: str) -> None:
        compile(content, str(target), "exec")

    with pytest.raises(SyntaxError):
        atomic_write_text_validated(
            target,
            "value = (\n",
            validator,
        )
    assert target.read_text(encoding="utf-8") == "value = 1\n"

    atomic_write_text_validated(
        target,
        "value = 2\n",
        validator,
    )
    assert target.read_text(encoding="utf-8") == "value = 2\n"


def test_json_manifest_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "phase.json"
    path.write_text(
        json.dumps(active_manifest()),
        encoding="utf-8",
    )
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert validate_manifest(loaded)["status"] == "ACTIVE"

def test_resume_loads_existing_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    manifest_path = tmp_path / "phase99a.json"
    manifest_path.write_text(
        json.dumps(active_manifest()),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        engine_module,
        "state_root",
        lambda: tmp_path / "state",
    )

    initial = LifecycleEngine(
        project_root,
        manifest_path,
        ApprovalSet(),
        resume=False,
        dry_run=True,
    )
    initial.state["status"] = "IMPLEMENTED"
    initial.state_path.write_text(
        json.dumps(initial.state),
        encoding="utf-8",
    )

    resumed = LifecycleEngine(
        project_root,
        manifest_path,
        ApprovalSet(),
        resume=True,
        dry_run=True,
    )
    assert resumed.run_dir == initial.run_dir
    assert resumed.state["status"] == "IMPLEMENTED"

