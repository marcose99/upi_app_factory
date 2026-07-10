from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.transformation_controller.phase46h import (
    REPO_TOKEN,
    STATE_TOKEN,
    expand_runtime_path,
    resolve_repo_root,
    verify_contract,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_expand_runtime_path_uses_contract_tokens(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    assert expand_runtime_path(REPO_TOKEN, repo, state) == repo
    assert expand_runtime_path(STATE_TOKEN, repo, state) == state
    assert (
        expand_runtime_path(
            f"{REPO_TOKEN}/config/example.json",
            repo,
            state,
        )
        == repo / "config/example.json"
    )


def test_expand_runtime_path_rejects_absolute_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Absolute runtime paths"):
        expand_runtime_path("/tmp/forbidden", tmp_path, tmp_path / "state")


def test_resolve_repo_root_walks_from_child(tmp_path: Path) -> None:
    root = tmp_path / "factory"
    (root / "config").mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "config/display_identity_contract.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (root / "bin/upi-app-factory").write_text("", encoding="utf-8")
    child = root / "a/b/c"
    child.mkdir(parents=True)
    assert resolve_repo_root(child) == root


def test_verify_contract_accepts_path_neutral_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "factory"
    (root / "bin").mkdir(parents=True)
    (root / "bin/upi-app-factory").write_text("", encoding="utf-8")
    write_json(root / "config/display_identity_contract.json", {})
    write_json(
        root / "config/path_identity_contract.json",
        {
            "canonical_repo_token": REPO_TOKEN,
            "canonical_state_token": STATE_TOKEN,
            "physical_checkout_rename": "NOT_PERFORMED",
            "remote_repository_rename": "NOT_PERFORMED",
            "resolution_probes": [
                {"name": "repo", "value": REPO_TOKEN},
                {"name": "config", "value": f"{REPO_TOKEN}/config"},
                {"name": "state", "value": STATE_TOKEN},
            ],
        },
    )
    write_json(
        root / "policies/path_neutral_runtime_policy.json",
        {"absolute_checkout_paths_allowed": False},
    )
    write_json(
        root / "config/identity_compatibility_runtime.json",
        {
            "path_resolution_contract": "config/path_identity_contract.json",
            "runtime_root_posture": "PATH_NEUTRAL",
        },
    )
    monkeypatch.setenv("UPI_APP_FACTORY_STATE_DIR", str(tmp_path / "state"))
    report = verify_contract(root)
    assert report["status"] == "PASSED"
    assert report["physical_checkout_rename"] == "NOT_PERFORMED"

def test_verify_contract_rejects_arbitrary_absolute_contract_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "factory"
    (root / "bin").mkdir(parents=True)
    (root / "bin/upi-app-factory").write_text("", encoding="utf-8")
    write_json(root / "config/display_identity_contract.json", {})
    write_json(
        root / "config/path_identity_contract.json",
        {
            "canonical_repo_token": REPO_TOKEN,
            "canonical_state_token": STATE_TOKEN,
            "physical_checkout_rename": "NOT_PERFORMED",
            "remote_repository_rename": "NOT_PERFORMED",
            "resolution_probes": [
                {"name": "repo", "value": REPO_TOKEN},
                {"name": "config", "value": "/tmp/not-governed"},
                {"name": "state", "value": STATE_TOKEN},
            ],
        },
    )
    write_json(
        root / "policies/path_neutral_runtime_policy.json",
        {"absolute_checkout_paths_allowed": False},
    )
    write_json(
        root / "config/identity_compatibility_runtime.json",
        {
            "path_resolution_contract": (
                "config/path_identity_contract.json"
            ),
            "runtime_root_posture": "PATH_NEUTRAL",
        },
    )
    monkeypatch.setenv(
        "UPI_APP_FACTORY_STATE_DIR",
        str(tmp_path / "state"),
    )
    with pytest.raises(ValueError, match="Absolute checkout path"):
        verify_contract(root)

