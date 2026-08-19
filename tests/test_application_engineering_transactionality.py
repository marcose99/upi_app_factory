from __future__ import annotations

import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

import pytest

from factory.application_engineering import deep_composer
from factory.application_engineering.deep_composer import DeepApplicationComposer
from factory.application_engineering.transactional_publish import (
    DirectoryPublication,
    publish_directories,
)
from factory.operator_portal.deep_portal_integration import (
    APP_ID,
    DeepPortalIntegration,
    PortalRequirements,
)
from scripts import run_portal_requirements_driven_application_engineering as adapter


ROOT = Path(__file__).resolve().parents[1]


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _requirements(path: Path) -> Path:
    path.write_text(
        """# Failed debit dispute application

Build a deterministic local application for failed-debit disputes with health,
readiness, evidence, investigation, resolution, closure, and audit capabilities.
All payment ecosystems are mocked and real payment calls remain disabled.
""",
        encoding="utf-8",
    )
    return path


def _config(tmp_path: Path, *, replace_existing: bool = True) -> adapter.AdapterConfig:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return adapter.AdapterConfig(
        requirements=_requirements(tmp_path / "requirements.md"),
        app_id=APP_ID,
        output_root=workspace / "approved" / "generated_app",
        evidence_root=workspace / "approved" / "engineering_evidence",
        approval_mode="human-gated",
        approval_token=adapter.APPROVAL_TOKEN,
        mock_safe=True,
        plan_only=False,
        replace_existing=replace_existing,
        factory_root=tmp_path,
        workspace_root=workspace,
        engineering_profile="local-deep-v1",
        register_with_portfolio=False,
    )


def _passing_gate(*_: object, **__: object) -> dict[str, object]:
    return {
        "decision": "GO",
        "mandatory_gate_passed": True,
        "requirements_sha256": "0" * 64,
        "obligation_count": 1,
        "summary": {},
        "artifact_root": "local-test-artifact",
        "artifact_checksums": {},
    }


def test_adapter_config_does_not_delete_previous_approved_output(tmp_path: Path) -> None:
    portal = DeepPortalIntegration(project_root=tmp_path)
    requirements_path = _requirements(tmp_path / "requirements.md")
    requirements = PortalRequirements(
        text=requirements_path.read_text(encoding="utf-8"),
        source_label="requirements.md",
        source_path=requirements_path,
        sha256="a" * 64,
    )
    previous = (
        portal.runtime_root
        / "approved_runs"
        / requirements.sha256[:16]
        / "generated_app"
    )
    (previous / "published.txt").parent.mkdir(parents=True)
    (previous / "published.txt").write_bytes(b"previous-good-output\x00")
    before = _snapshot(previous)

    config = portal._adapter_config(requirements, plan_only=False, approved=True)

    assert config.output_root == previous
    assert _snapshot(previous) == before


def test_composer_failure_preserves_previous_output_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "generated_app"
    previous = output_root / APP_ID
    (previous / "evidence").mkdir(parents=True)
    (previous / "published.bin").write_bytes(b"previous-good-output\x00")
    (previous / "evidence" / "result.json").write_bytes(b'{"status":"good"}\n')
    before = _snapshot(previous)
    real_write = deep_composer._write_text
    writes = 0

    def fail_during_generation(path: Path, content: str) -> None:
        nonlocal writes
        writes += 1
        real_write(path, content)
        if writes == 4:
            raise OSError("injected composer failure")

    monkeypatch.setattr(deep_composer, "_write_text", fail_during_generation)

    with pytest.raises(OSError, match="injected composer failure"):
        DeepApplicationComposer(tmp_path).compose(
            requirements_ir={"traceability": [], "source_documents": []},
            output_root=output_root,
            app_id=APP_ID,
            replace_existing=True,
        )

    assert _snapshot(previous) == before
    assert not list(output_root.glob(f".{APP_ID}.staging.*"))


def test_multi_directory_publish_rolls_back_all_destinations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "application"
    second = tmp_path / "evidence"
    first_candidate = tmp_path / ".application.staging.test"
    second_candidate = tmp_path / ".evidence.staging.test"
    for path, value in (
        (first, b"old-app"),
        (second, b"old-evidence"),
        (first_candidate, b"new-app"),
        (second_candidate, b"new-evidence"),
    ):
        path.mkdir()
        (path / "value.bin").write_bytes(value)
    first_before = _snapshot(first)
    second_before = _snapshot(second)
    real_replace = Path.replace

    def fail_second_publish(path: Path, target: Path) -> Path:
        if path == second_candidate and target == second:
            raise OSError("injected publish failure")
        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_second_publish)

    with pytest.raises(OSError, match="injected publish failure"):
        publish_directories(
            [
                DirectoryPublication(first_candidate, first),
                DirectoryPublication(second_candidate, second),
            ]
        )

    assert _snapshot(first) == first_before
    assert _snapshot(second) == second_before
    assert not list(tmp_path.glob(".*.backup.*"))


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM publication guarantee is POSIX-only")
def test_sigterm_during_publish_restores_a_complete_destination(tmp_path: Path) -> None:
    destination = tmp_path / "application"
    candidate = tmp_path / ".application.staging.sigterm"
    for root, version in ((destination, "old"), (candidate, "new")):
        (root / "nested").mkdir(parents=True)
        (root / "version.txt").write_text(version, encoding="utf-8")
        (root / "nested" / "payload.bin").write_bytes(version.encode() * 128)
    old_snapshot = _snapshot(destination)
    new_snapshot = _snapshot(candidate)
    ready = tmp_path / "backup-created"
    child_code = """
import sys
import time
from pathlib import Path

from factory.application_engineering.transactional_publish import (
    DirectoryPublication,
    publish_directories,
)

root = Path(sys.argv[1])
destination = root / "application"
candidate = root / ".application.staging.sigterm"
ready = root / "backup-created"
real_replace = Path.replace

def pause_after_backup(path, target):
    result = real_replace(path, target)
    if path == destination and target.name.startswith(".application.backup."):
        ready.write_text("ready", encoding="utf-8")
        time.sleep(30)
    return result

Path.replace = pause_after_backup
publish_directories([DirectoryPublication(candidate, destination)])
"""
    process = subprocess.Popen(
        [sys.executable, "-c", child_code, str(tmp_path)],
        cwd=ROOT,
    )
    try:
        for _ in range(500):
            if ready.exists() or process.poll() is not None:
                break
            time.sleep(0.01)
        assert ready.exists(), "child did not reach the backup-to-candidate rename window"
        process.send_signal(signal.SIGTERM)
        return_code = process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert return_code == -signal.SIGTERM
    assert destination.is_dir()
    assert _snapshot(destination) in (old_snapshot, new_snapshot)
    assert not list(tmp_path.glob(".application.backup.*"))


def test_gate_rejection_preserves_previous_application_and_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    (config.output_root / "published.txt").parent.mkdir(parents=True)
    (config.output_root / "published.txt").write_bytes(b"previous-good-app")
    (config.evidence_root / "good" / "result.json").parent.mkdir(parents=True)
    (config.evidence_root / "good" / "result.json").write_bytes(b"previous-good-evidence")
    output_before = _snapshot(config.output_root)
    evidence_before = _snapshot(config.evidence_root)
    rejected = _passing_gate()
    rejected["decision"] = "NO-GO"
    rejected["mandatory_gate_passed"] = False
    monkeypatch.setattr(adapter, "_run_native_capability_gate", lambda *_: rejected)

    with pytest.raises(adapter.AdapterError, match="did not prove 100 percent"):
        adapter.run(config)

    assert _snapshot(config.output_root) == output_before
    assert _snapshot(config.evidence_root) == evidence_before


def test_deep_mirror_failure_preserves_all_previous_publications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    actual = config.output_root
    canonical = (
        tmp_path / "workspace" / "deep_engineering_campaign" / "generated_app" / APP_ID
    )
    evidence = config.evidence_root / "previous-good"
    for root, value in (
        (actual, b"previous-app"),
        (canonical, b"previous-canonical"),
        (evidence, b"previous-evidence"),
    ):
        root.mkdir(parents=True)
        (root / "published.bin").write_bytes(value)
    before = {root: _snapshot(root) for root in (actual, canonical, evidence)}
    monkeypatch.setattr(adapter, "_run_native_capability_gate", _passing_gate)
    monkeypatch.setattr(
        shutil,
        "copytree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected mirror failure")),
    )

    with pytest.raises(OSError, match="injected mirror failure"):
        adapter.run(config)

    assert {root: _snapshot(root) for root in before} == before
    assert not list(actual.parent.glob(f".{actual.name}.staging.*"))
    assert not list(canonical.parent.glob(f".{canonical.name}.staging.*"))
    assert not list(config.evidence_root.glob(".portal_deep_*.staging.*"))


def test_materialization_failure_preserves_previous_application_and_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = adapter.AdapterConfig(
        requirements=_requirements(tmp_path / "requirements.md"),
        app_id="upi_dispute_resolution",
        output_root=tmp_path / "published_application",
        evidence_root=tmp_path / "publication_evidence",
        approval_mode="human-gated",
        approval_token=adapter.APPROVAL_TOKEN,
        mock_safe=True,
        plan_only=False,
        replace_existing=True,
        factory_root=ROOT,
        workspace_root=tmp_path,
        engineering_profile="authoritative-failed-debit-v1",
        register_with_portfolio=False,
    )
    (config.output_root / "published.bin").parent.mkdir()
    (config.output_root / "published.bin").write_bytes(b"previous-good-app")
    previous_evidence = config.evidence_root / "previous-good"
    previous_evidence.mkdir(parents=True)
    (previous_evidence / "result.json").write_bytes(b"previous-good-evidence")
    output_before = _snapshot(config.output_root)
    evidence_before = _snapshot(previous_evidence)
    monkeypatch.setattr(adapter, "_run_native_capability_gate", _passing_gate)
    monkeypatch.setattr(
        adapter,
        "materialize_generated_application_artifacts",
        lambda **_: (_ for _ in ()).throw(OSError("injected materialization failure")),
    )

    with pytest.raises(OSError, match="injected materialization failure"):
        adapter.run(config)

    assert _snapshot(config.output_root) == output_before
    assert _snapshot(previous_evidence) == evidence_before
    assert not list(tmp_path.glob(".published_application.staging.*"))


def test_verification_failure_preserves_previous_application_and_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = adapter.AdapterConfig(
        requirements=_requirements(tmp_path / "requirements.md"),
        app_id=APP_ID,
        output_root=tmp_path / "published_application",
        evidence_root=tmp_path / "publication_evidence",
        approval_mode="human-gated",
        approval_token=adapter.APPROVAL_TOKEN,
        mock_safe=True,
        plan_only=False,
        replace_existing=True,
        factory_root=tmp_path,
        workspace_root=tmp_path,
        engineering_profile="compatibility",
        register_with_portfolio=False,
    )
    (config.output_root / "published.bin").parent.mkdir()
    (config.output_root / "published.bin").write_bytes(b"previous-good-app")
    previous_evidence = config.evidence_root / "previous-good"
    previous_evidence.mkdir(parents=True)
    (previous_evidence / "result.json").write_bytes(b"previous-good-evidence")
    output_before = _snapshot(config.output_root)
    evidence_before = _snapshot(previous_evidence)
    monkeypatch.setattr(adapter, "_run_native_capability_gate", _passing_gate)
    monkeypatch.setattr(
        adapter,
        "_capture_openapi",
        lambda **_: {"document": {"paths": {}}, "inventory": {"endpoint_inventory": []}},
    )
    monkeypatch.setattr(
        adapter,
        "_execute_generated_tests",
        lambda **_: {"go_gate": "NO-GO", "exit_code": 1},
    )

    with pytest.raises(adapter.AdapterError, match="generated application tests failed"):
        adapter.run(config)

    assert _snapshot(config.output_root) == output_before
    assert _snapshot(previous_evidence) == evidence_before
    assert not list(tmp_path.glob(".published_application.staging.*"))


def test_successful_deep_run_replaces_only_after_complete_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    (config.output_root / "obsolete.txt").parent.mkdir(parents=True)
    (config.output_root / "obsolete.txt").write_text("old", encoding="utf-8")
    monkeypatch.setattr(adapter, "_run_native_capability_gate", _passing_gate)

    result = adapter.run(config)

    published = config.output_root / APP_ID
    assert result["status"] == adapter.SUCCESS_STATUS
    assert not (config.output_root / "obsolete.txt").exists()
    assert (published / "evidence" / "generation_manifest.json").is_file()
    assert Path(str(result["evidence_directory"]), "result.json").is_file()
    assert not list(config.output_root.parent.glob(f".{config.output_root.name}.staging.*"))
