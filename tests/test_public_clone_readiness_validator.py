from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.validate_public_clone_readiness import (
    _check_secrets,
    _run_git_ls_files,
    _secret_findings_bytes,
    validate,
)


def test_public_clone_readiness_validator_passes_repository() -> None:
    root = Path(__file__).resolve().parents[1]
    report = validate(root, "Apache-2.0")
    assert report["status"] == "passed", json.dumps(report, indent=2)
    check_names = {check["name"] for check in report["checks"]}
    assert {
        "license_notice",
        "personal_paths_and_stale_identities",
        "tracked_workspace_state_policy",
        "openapi_and_test_evidence_hooks",
        "secrets",
    } <= check_names


def test_public_clone_readiness_cli_writes_json_output(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "public-readiness.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/validate_public_clone_readiness.py"),
            "--repo",
            str(root),
            "--license",
            "Apache-2.0",
            "--json-output",
            str(output),
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "passed"


def test_public_clone_readiness_fails_closed_outside_git(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/validate_public_clone_readiness.py"),
            "--repo",
            str(tmp_path),
            "--license",
            "Apache-2.0",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode != 0
    assert '"status": "failed"' in completed.stdout
    assert "fail_closed" in completed.stdout


def test_secret_scanner_handles_common_utf16_and_binary_credentials() -> None:
    fixtures = (
        b"ghp_" + b"ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
        b"eyJabcdefghijk." + b"abcdefghijkl.abcdefghijkl",
        ("password=" + "abcdefghijklmnopqrstuv").encode("utf-16"),
        b"\x00\xffBINARY\x00client_secret=" + b"abcdefghijklmnopqrstuv\x00",
        b"github_" + b"pat_11AA22BB33CC44DD55EE66_FineGrainedTokenBody1234567890",
        b"AI" + b"za" + (b"A" * 35),
        b"NPM_TOKEN=npm_" + b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJ",
        b"AWS_ACCESS_KEY_ID=ASIA" + b"ABCDEFGHIJKLMNOP",
        b"auth_token=" + b"0123456789abcdefghijklmnopqrstuv",
        b"-----BEGIN ENCRYPTED " + b"PRIVATE KEY-----\nMIIBfixture",
        b"\x00binary\x00-----BEGIN ENCRYPTED " + b"PRIVATE KEY-----\x00",
        b"ACME_CLIENT_SECRET=" + b"Z7vQ2mN9xK4pR8sT6wY3cF1hJ5dL0bG2",
        b"DATABASE_URL=postgresql://service:" + b"V7mQ2xN9kR4pT8wY@db.invalid/app",
    )
    for payload in fixtures:
        assert _secret_findings_bytes("fixture", payload)


def test_generic_secret_detector_spares_low_entropy_values() -> None:
    fixtures = (
        b"private_key=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        b"credential=abcabcabcabcabcabcabcabcabcabc",
    )
    for payload in fixtures:
        assert not _secret_findings_bytes("fixture", payload)


@pytest.mark.parametrize(
    "credential",
    [
        "NPM_TOKEN=" + "npm_" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJ",
        "AWS_ACCESS_KEY_ID=" + "ASIA" + "ABCDEFGHIJKLMNOP",
        "auth_token=" + "0123456789abcdefghijklmnopqrstuv",
        "UNLISTED_SERVICE_CREDENTIAL=" + "Z7vQ2mN9xK4pR8sT6wY3cF1hJ5dL0bG2",
        "DATABASE_URL=postgresql://service:" + "V7mQ2xN9kR4pT8wY@db.invalid/app",
    ],
)
def test_secret_scanner_rejects_credentials_in_worktree_and_history(
    tmp_path: Path, credential: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True
    )
    historical = repo / "historical.env"
    historical.write_text(credential + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "historical.env"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "credential history"], cwd=repo, check=True)
    historical.write_text("REDACTED=true\n", encoding="utf-8")
    current = repo / "current.env"
    current.write_text(credential + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "redact history only"], cwd=repo, check=True)

    check = _check_secrets(repo, _run_git_ls_files(repo))

    assert check.status == "failed"
    assert any("current.env" in detail for detail in check.details)
    assert any("git-blob:" in detail for detail in check.details)


def test_secret_scanner_rejects_encrypted_pkcs8_in_worktree_and_history(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True
    )
    key = "-----BEGIN ENCRYPTED " + "PRIVATE KEY-----\nMIIBfixture\n"
    historical = repo / "historical.pem"
    historical.write_text(key, encoding="utf-8")
    subprocess.run(["git", "add", "historical.pem"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "key history"], cwd=repo, check=True)
    historical.write_text("REDACTED\n", encoding="utf-8")
    current = repo / "current.bin"
    current.write_bytes(b"\x00binary\x00" + key.encode())
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "redact historical key"], cwd=repo, check=True)

    check = _check_secrets(repo, _run_git_ls_files(repo))

    assert check.status == "failed"
    assert any("current.bin" in detail for detail in check.details)
    assert any("git-blob:" in detail for detail in check.details)
