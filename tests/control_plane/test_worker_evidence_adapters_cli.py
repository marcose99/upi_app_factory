from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from tools.factory_control_plane.adapters import (
    AutonomousSupervisorAdapter,
    LifecycleOrchestratorAdapter,
    closure_attestation,
)
from tools.factory_control_plane.common import ControlPlaneError
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.evidence import seal_directory, verify_seal
from tools.factory_control_plane.fs_guard import FilesystemGuard
import tools.factory_control_plane.fs_guard as fs_guard_module
import tools.factory_control_plane.evidence as evidence_module
from tools.factory_control_plane.worker import InboxWorker


ROOT = Path(__file__).resolve().parents[2]
SELF_TEST = ROOT / "config/control_plane/campaigns/control_plane_self_test.json"
POLICY = ROOT / "config/control_plane/standing_policy.json"


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SELF_TEST.read_text(encoding="utf-8")))


def test_inbox_worker_success_and_quarantine(tmp_path: Path) -> None:
    engine = ControlPlaneEngine(ROOT, tmp_path / "state", POLICY)
    worker = InboxWorker(tmp_path / "inbox", engine)
    try:
        shutil.copy2(SELF_TEST, tmp_path / "inbox/pending/self.json")
        assert worker.run_once()["status"] == "completed"
        assert (tmp_path / "inbox/completed/self.json.result.json").is_file()
        bad = _payload()
        bad["unexpected"] = True
        (tmp_path / "inbox/pending/bad.json").write_text(json.dumps(bad), encoding="utf-8")
        failed = worker.run_once()
        assert failed["status"] == "failed"
        assert (tmp_path / "inbox/failed/bad.json").is_file()
        assert (tmp_path / "inbox/failed/bad.json.result.json").is_file()
    finally:
        engine.close()


def test_evidence_sealing_and_symlink_rejection(tmp_path: Path) -> None:
    source = tmp_path / "evidence"
    source.mkdir()
    (source / "result.json").write_text("{}", encoding="utf-8")
    sealed = seal_directory(source, tmp_path / "sealed", tmp_path / "anchors")
    assert Path(sealed["archive"]).is_file()
    (source / "link").symlink_to(source / "result.json")
    with pytest.raises(ControlPlaneError, match="symlink"):
        seal_directory(source, tmp_path / "sealed2", tmp_path / "anchors2")


def test_multi_root_publication_rolls_back_every_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("one", "two"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "value.txt").write_text("old", encoding="utf-8")
    guard = FilesystemGuard(tmp_path)
    roots = [guard.directory("one"), guard.directory("two")]
    stages = [guard.private_stage(root, ".stage") for root in roots]
    try:
        for stage in stages:
            (Path(stage.proc_path) / "value.txt").write_text("new", encoding="utf-8")
        real_exchange = fs_guard_module._rename_exchange
        calls = 0

        def fail_second(source: str, destination: str, parent_fd: int) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected second-root publication failure")
            real_exchange(source, destination, parent_fd)

        monkeypatch.setattr(fs_guard_module, "_rename_exchange", fail_second)
        with pytest.raises(ControlPlaneError, match="promotion"):
            guard.promote_many(tuple((root, ".stage") for root in roots))
        assert (tmp_path / "one/value.txt").read_bytes() == b"old"
        assert (tmp_path / "two/value.txt").read_bytes() == b"old"
    finally:
        for stage in stages:
            stage.close()
        for root in roots:
            root.close()
        guard.close()


def test_sealed_archive_bytes_match_published_manifest(tmp_path: Path) -> None:
    source = tmp_path / "evidence"
    source.mkdir()
    payload = b"captured once"
    (source / "result.json").write_bytes(payload)
    sealed = seal_directory(source, tmp_path / "sealed", tmp_path / "anchors")
    manifest = json.loads(Path(sealed["manifest"]).read_text(encoding="utf-8"))
    assert manifest == {"result.json": hashlib.sha256(payload).hexdigest()}


def test_evidence_archive_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first" / "evidence"
    second = tmp_path / "second" / "evidence"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "result.json").write_text("{}\n", encoding="utf-8")
    (second / "result.json").write_text("{}\n", encoding="utf-8")
    first_seal = seal_directory(first, tmp_path / "sealed-first", tmp_path / "anchors-first")
    second_seal = seal_directory(second, tmp_path / "sealed-second", tmp_path / "anchors-second")
    assert Path(first_seal["archive"]).read_bytes() == Path(second_seal["archive"]).read_bytes()
    assert first_seal["archive_sha256"] == second_seal["archive_sha256"]


@pytest.mark.parametrize("failed_write", [1, 2, 3])
def test_interrupted_seal_publication_is_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_write: int
) -> None:
    source = tmp_path / "evidence"
    source.mkdir()
    (source / "result.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "sealed"
    real_write = evidence_module._atomic_write
    calls = 0

    def fail_selected(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == failed_write:
            raise OSError("injected seal staging failure")
        real_write(path, payload)

    monkeypatch.setattr(evidence_module, "_atomic_write", fail_selected)
    with pytest.raises(OSError, match="injected"):
        seal_directory(source, output, tmp_path / "anchors")
    assert not (output / "evidence.seal").exists()
    monkeypatch.setattr(evidence_module, "_atomic_write", real_write)
    assert Path(seal_directory(source, output, tmp_path / "anchors")["archive"]).is_file()


@pytest.mark.parametrize("artifact", ["manifest", "archive", "checksum", "anchor"])
def test_existing_seal_rejects_each_tampered_artifact(
    tmp_path: Path, artifact: str
) -> None:
    source = tmp_path / "evidence"
    source.mkdir()
    (source / "result.json").write_text("{}", encoding="utf-8")
    sealed = seal_directory(source, tmp_path / "sealed", tmp_path / "anchors")
    target = Path(sealed[artifact])
    target.write_bytes(target.read_bytes() + b"tampered")
    with pytest.raises(ControlPlaneError, match="integrity"):
        verify_seal(
            Path(sealed["manifest"]),
            Path(sealed["archive"]),
            Path(sealed["checksum"]),
            Path(sealed["anchor"]),
        )


def test_coherent_state_root_rewrite_is_rejected_by_detached_anchor(
    tmp_path: Path,
) -> None:
    source = tmp_path / "state/evidence"
    source.mkdir(parents=True)
    (source / "result.json").write_text("original", encoding="utf-8")
    sealed = seal_directory(source, tmp_path / "state/sealed", tmp_path / "anchors")
    anchor_before = Path(sealed["anchor"]).read_bytes()

    shutil.rmtree(tmp_path / "state/sealed/evidence.seal")
    (source / "result.json").write_text("forged", encoding="utf-8")
    with pytest.raises(ControlPlaneError, match="trust anchor already exists"):
        seal_directory(source, tmp_path / "state/sealed", tmp_path / "anchors")
    assert Path(sealed["anchor"]).read_bytes() == anchor_before


def test_adapter_contracts() -> None:
    lifecycle = LifecycleOrchestratorAdapter()
    supervisor = AutonomousSupervisorAdapter()
    assert lifecycle.available()
    assert supervisor.available()
    assert lifecycle.contract()["entrypoint"] == "bin/upi-app-factory-lifecycle"
    assert closure_attestation("phase46a", Path("evidence/phase46a"))[
        "regeneration"
    ] == "forbidden during later campaign execution"


def test_cli_self_test_and_rerun_behavior(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "bin/upi-app-factory-control-plane",
        "--state-root",
        str(tmp_path / "state"),
        "run",
        str(SELF_TEST),
    ]
    first = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    first_payload = json.loads(first.stdout)
    assert first_payload["status"] == "closed"
    second = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    second_payload = json.loads(second.stdout)
    assert second_payload["status"] == "closed"
    assert second_payload["summary"]["completed_activities"] == 3


def test_cli_default_state_root_is_outside_repository(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment.pop("XDG_STATE_HOME", None)
    environment.pop("UPI_APP_FACTORY_CONTROL_PLANE_STATE", None)
    command = [
        sys.executable,
        "bin/upi-app-factory-control-plane",
        "run",
        str(SELF_TEST),
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "closed"
    from tools.factory_control_plane.common import sha256_text

    checkout_id = sha256_text(str(ROOT.resolve()))[:24]
    state_root = home / ".local/state/upi_app_factory/control_plane/checkouts" / checkout_id
    assert (state_root / "control_plane.sqlite3").is_file()


def test_default_state_root_isolated_between_checkouts(tmp_path: Path) -> None:
    from tools.factory_control_plane.common import default_state_root

    first = tmp_path / "clone-a"
    second = tmp_path / "clone-b"
    first.mkdir()
    second.mkdir()
    assert default_state_root(first) != default_state_root(second)
    assert default_state_root(first) == default_state_root(first)
    assert not (ROOT / ".control_plane_state").exists()


def test_policy_explain_cli(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "bin/upi-app-factory-control-plane",
        "--state-root",
        str(tmp_path / "state"),
        "policy-explain",
        "create_tag",
        "LOW",
    ]
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "pause"
