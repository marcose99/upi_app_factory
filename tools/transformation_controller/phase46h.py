from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

REPO_TOKEN = "${REPO_ROOT}"
STATE_TOKEN = "${STATE_ROOT}"


def contains_unapproved_absolute_path(value: object) -> bool:
    if isinstance(value, str):
        if value.startswith("${"):
            return False
        return Path(value).expanduser().is_absolute()
    if isinstance(value, dict):
        return any(
            contains_unapproved_absolute_path(item)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(
            contains_unapproved_absolute_path(item)
            for item in value
        )
    return False


def load_object(path: Path, label: str) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object")
    return raw


def resolve_repo_root(anchor: Path | None = None) -> Path:
    override = os.environ.get("UPI_APP_FACTORY_REPO_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / "config/display_identity_contract.json").is_file():
            raise ValueError("UPI_APP_FACTORY_REPO_ROOT is not a factory checkout")
        return root

    current = (anchor or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (
            (candidate / "config/display_identity_contract.json").is_file()
            and (candidate / "bin/upi-app-factory").is_file()
        ):
            return candidate
    raise ValueError("Unable to resolve the UPI App Factory repository root")


def resolve_state_root() -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local/state"
    return (base / "upi_app_factory").resolve()


def expand_runtime_path(value: str, repo_root: Path, state_root: Path) -> Path:
    if value == REPO_TOKEN:
        return repo_root
    if value == STATE_TOKEN:
        return state_root
    if value.startswith(REPO_TOKEN + "/"):
        return repo_root / value[len(REPO_TOKEN) + 1 :]
    if value.startswith(STATE_TOKEN + "/"):
        return state_root / value[len(STATE_TOKEN) + 1 :]
    path = Path(value).expanduser()
    if path.is_absolute():
        raise ValueError("Absolute runtime paths are forbidden by the path contract")
    return repo_root / path


def verify_contract(project_root: Path) -> dict[str, Any]:
    contract_path = project_root / "config/path_identity_contract.json"
    policy_path = project_root / "policies/path_neutral_runtime_policy.json"
    runtime_path = project_root / "config/identity_compatibility_runtime.json"

    contract = load_object(contract_path, "Path identity contract")
    policy = load_object(policy_path, "Path-neutral runtime policy")
    runtime = load_object(runtime_path, "Identity compatibility runtime")

    if contract.get("canonical_repo_token") != REPO_TOKEN:
        raise ValueError("Unexpected canonical repository token")
    if contract.get("canonical_state_token") != STATE_TOKEN:
        raise ValueError("Unexpected canonical state token")
    if contract.get("physical_checkout_rename") != "NOT_PERFORMED":
        raise ValueError("Physical checkout rename must remain deferred")
    if contract.get("remote_repository_rename") != "NOT_PERFORMED":
        raise ValueError("Remote repository rename must remain deferred")
    if policy.get("absolute_checkout_paths_allowed") is not False:
        raise ValueError("Absolute checkout paths must be prohibited")
    if runtime.get("path_resolution_contract") != "config/path_identity_contract.json":
        raise ValueError("Runtime does not reference the path contract")
    if runtime.get("runtime_root_posture") != "PATH_NEUTRAL":
        raise ValueError("Runtime path-neutral posture is not active")

    active_contracts = {
        "contract": contract,
        "policy": policy,
        "runtime": runtime,
    }
    if contains_unapproved_absolute_path(active_contracts):
        raise ValueError(
            "Absolute checkout path leaked into active path contracts"
        )

    repo_root = resolve_repo_root(project_root)
    state_root = resolve_state_root()
    probes = contract.get("resolution_probes")
    if not isinstance(probes, list) or len(probes) < 3:
        raise ValueError("Path contract requires at least three resolution probes")

    resolved = []
    for item in probes:
        if not isinstance(item, dict):
            raise ValueError("Path probe must be an object")
        raw = item.get("value")
        if not isinstance(raw, str):
            raise ValueError("Path probe value must be a string")
        resolved.append(
            {
                "name": item.get("name"),
                "value": raw,
                "resolved": str(expand_runtime_path(raw, repo_root, state_root)),
            }
        )

    return {
        "status": "PASSED",
        "phase": "46H",
        "repo_root": str(repo_root),
        "state_root": str(state_root),
        "resolution_probes": resolved,
        "physical_checkout_rename": "NOT_PERFORMED",
        "remote_repository_rename": "NOT_PERFORMED",
        "llm_calls": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Phase 46H path-neutral runtime contracts"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    report = verify_contract(parsed.project_root.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
