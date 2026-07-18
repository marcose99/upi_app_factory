from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from upi_factory.capstone.phase68 import Phase68Error, run_recipient_replay, verify_manifest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "factory_governance" / "phase68_70" / "recipient_fixture"


def test_clean_recipient_replay_and_verifier_pass(tmp_path: Path) -> None:
    output = tmp_path / "recipient_replay"

    result = run_recipient_replay(project_root=ROOT, fixture_root=FIXTURE, output_root=output)
    verification = verify_manifest(output / "content_manifest.json")

    assert result["status"] == "PASS"
    assert result["fictional_data_only"] is True
    assert result["official_certification_claimed"] is False
    assert result["live_provider_calls_performed"] is False
    assert (output / "handoff_bundle.zip").is_file()
    assert verification["status"] == "PASS"
    assert verification["verified_payload_records"] >= 7


def test_tampered_payload_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "recipient_replay"
    run_recipient_replay(project_root=ROOT, fixture_root=FIXTURE, output_root=output)

    payload = output / "payload" / "requirements_intake.json"
    data = json.loads(payload.read_text(encoding="utf-8"))
    data["scenario"] = "tampered fictional scenario"
    payload.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(Phase68Error, match="Payload hash mismatch"):
        verify_manifest(output / "content_manifest.json")


def test_manifest_hash_tamper_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "recipient_replay"
    run_recipient_replay(project_root=ROOT, fixture_root=FIXTURE, output_root=output)

    manifest_path = output / "content_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "PASS-TAMPERED"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(Phase68Error, match="Manifest hash mismatch"):
        verify_manifest(manifest_path)


def test_path_traversal_manifest_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "recipient_replay"
    run_recipient_replay(project_root=ROOT, fixture_root=FIXTURE, output_root=output)

    manifest_path = output / "content_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("manifest_sha256")
    manifest["payload_records"][0]["path"] = "../outside.json"
    raw = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    import hashlib

    manifest["manifest_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(Phase68Error, match="Unsafe payload path"):
        verify_manifest(manifest_path)


def test_symlink_fixture_is_rejected(tmp_path: Path) -> None:
    fixture_copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture_copy)
    (fixture_copy / "linked.json").symlink_to(fixture_copy / "requirements_intake.json")

    with pytest.raises(Phase68Error, match="Symlink is not allowed"):
        run_recipient_replay(project_root=ROOT, fixture_root=fixture_copy, output_root=tmp_path / "out")


def test_cli_replay_and_validator_pass(tmp_path: Path) -> None:
    output = tmp_path / "recipient_replay"
    replay = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase68_recipient_replay.py",
            "--output-root",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr

    validate = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase68_reproducible_evaluator_recipient.py",
            "--manifest",
            str(output / "content_manifest.json"),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    assert json.loads(validate.stdout)["status"] == "PASS"
