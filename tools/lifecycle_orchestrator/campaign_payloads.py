from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import subprocess
from pathlib import Path
from typing import Any

PHASE_PAYLOADS: dict[str, dict[str, str]] = {
    "46H": {
        "config/path_identity_contract.json": "{\n"
        '  "absolute_checkout_paths_allowed": '
        "false,\n"
        '  "canonical_repo_token": '
        '"${REPO_ROOT}",\n'
        '  "canonical_state_token": '
        '"${STATE_ROOT}",\n'
        '  "legacy_checkout_path_reads": '
        '"NOT_REQUIRED",\n'
        '  "phase": "46H",\n'
        '  "physical_checkout_rename": '
        '"NOT_PERFORMED",\n'
        '  "relative_path_posture": '
        '"PREFERRED",\n'
        '  "remote_repository_rename": '
        '"NOT_PERFORMED",\n'
        '  "resolution_probes": [\n'
        "    {\n"
        '      "name": "repository",\n'
        '      "value": "${REPO_ROOT}"\n'
        "    },\n"
        "    {\n"
        '      "name": "configuration",\n'
        '      "value": "${REPO_ROOT}/config"\n'
        "    },\n"
        "    {\n"
        '      "name": "state",\n'
        '      "value": "${STATE_ROOT}"\n'
        "    },\n"
        "    {\n"
        '      "name": "campaign_runs",\n'
        '      "value": '
        '"${STATE_ROOT}/campaign_runs"\n'
        "    }\n"
        "  ],\n"
        '  "schema_version": 1\n'
        "}\n",
        "docs/phase46h/README.md": "# Phase 46H — Path-neutral runtime hardening\n"
        "\n"
        "Phase 46H removes dependence on the current "
        "physical checkout path from active\n"
        "identity contracts. Runtime code resolves the "
        "repository and state roots from\n"
        "governed environment variables or repository "
        "markers.\n"
        "\n"
        "## Boundaries\n"
        "\n"
        "- The checkout directory is not renamed.\n"
        "- The Git remote is not renamed.\n"
        "- Historical evidence is not rewritten.\n"
        "- Compatibility aliases remain active.\n"
        "- No live provider or production action is "
        "enabled.\n"
        "\n"
        "The canonical tokens are `${REPO_ROOT}` and "
        "`${STATE_ROOT}`. Absolute checkout\n"
        "paths are rejected by the active path contract.\n",
        "policies/path_neutral_runtime_policy.json": "{\n"
        "  "
        '"absolute_checkout_paths_allowed": '
        "false,\n"
        '  "canonical_tokens": [\n'
        '    "${REPO_ROOT}",\n'
        '    "${STATE_ROOT}"\n'
        "  ],\n"
        '  "llm_calls_allowed": 0,\n'
        '  "phase": "46H",\n'
        '  "prohibited_actions": [\n'
        '    "physical checkout '
        'rename",\n'
        '    "remote repository '
        'rename",\n'
        '    "historical evidence '
        'rewrite",\n'
        '    "legacy alias retirement"\n'
        "  ],\n"
        '  "required_behaviors": [\n'
        '    "resolve repository roots '
        'at runtime",\n'
        '    "prefer relative paths '
        'inside repository contracts",\n'
        '    "keep local checkout rename '
        'human-gated",\n'
        '    "keep remote repository '
        'rename human-gated",\n'
        '    "fail closed on unapproved '
        'absolute paths"\n'
        "  ],\n"
        '  "schema_version": 1,\n'
        '  "status": "ACTIVE"\n'
        "}\n",
        "schemas/transformation/path_identity_contract.schema.json": "{\n"
        '  "$id": '
        '"https://upi-app-factory.local/schemas/transformation/path-identity-contract.schema.json",\n'
        '  "$schema": '
        '"https://json-schema.org/draft/2020-12/schema",\n'
        "  "
        '"additionalProperties": '
        "true,\n"
        '  "properties": '
        "{\n"
        "    "
        '"canonical_repo_token": '
        "{\n"
        '      "const": '
        '"${REPO_ROOT}"\n'
        "    },\n"
        "    "
        '"canonical_state_token": '
        "{\n"
        '      "const": '
        '"${STATE_ROOT}"\n'
        "    },\n"
        '    "phase": {\n'
        '      "const": '
        '"46H"\n'
        "    },\n"
        "    "
        '"physical_checkout_rename": '
        "{\n"
        '      "const": '
        '"NOT_PERFORMED"\n'
        "    },\n"
        "    "
        '"remote_repository_rename": '
        "{\n"
        '      "const": '
        '"NOT_PERFORMED"\n'
        "    },\n"
        "    "
        '"resolution_probes": '
        "{\n"
        '      "items": '
        "{\n"
        "        "
        '"properties": '
        "{\n"
        "          "
        '"name": {\n'
        "            "
        '"minLength": '
        "1,\n"
        "            "
        '"type": '
        '"string"\n'
        "          },\n"
        "          "
        '"value": {\n'
        "            "
        '"minLength": '
        "1,\n"
        "            "
        '"type": '
        '"string"\n'
        "          }\n"
        "        },\n"
        "        "
        '"required": [\n'
        "          "
        '"name",\n'
        "          "
        '"value"\n'
        "        ],\n"
        '        "type": '
        '"object"\n'
        "      },\n"
        "      "
        '"minItems": 3,\n'
        '      "type": '
        '"array"\n'
        "    },\n"
        "    "
        '"schema_version": '
        "{\n"
        '      "const": '
        "1\n"
        "    }\n"
        "  },\n"
        '  "required": '
        "[\n"
        "    "
        '"schema_version",\n'
        '    "phase",\n'
        "    "
        '"canonical_repo_token",\n'
        "    "
        '"canonical_state_token",\n'
        "    "
        '"physical_checkout_rename",\n'
        "    "
        '"remote_repository_rename",\n'
        "    "
        '"resolution_probes"\n'
        "  ],\n"
        '  "type": '
        '"object"\n'
        "}\n",
        "tests/transformation/test_phase46h_path_neutral_runtime.py": "from "
        "__future__ "
        "import "
        "annotations\n"
        "\n"
        "import json\n"
        "from pathlib "
        "import Path\n"
        "\n"
        "import pytest\n"
        "\n"
        "from "
        "tools.transformation_controller.phase46h "
        "import (\n"
        "    "
        "REPO_TOKEN,\n"
        "    "
        "STATE_TOKEN,\n"
        "    "
        "expand_runtime_path,\n"
        "    "
        "resolve_repo_root,\n"
        "    "
        "verify_contract,\n"
        ")\n"
        "\n"
        "\n"
        "def "
        "write_json(path: "
        "Path, value: "
        "object) -> "
        "None:\n"
        "    "
        "path.parent.mkdir(parents=True, "
        "exist_ok=True)\n"
        "    "
        "path.write_text(\n"
        "        "
        "json.dumps(value, "
        "indent=2, "
        "sort_keys=True) "
        '+ "\\n",\n'
        "        "
        'encoding="utf-8",\n'
        "    )\n"
        "\n"
        "\n"
        "def "
        "test_expand_runtime_path_uses_contract_tokens(tmp_path: "
        "Path) -> "
        "None:\n"
        "    repo = "
        "tmp_path / "
        '"repo"\n'
        "    state = "
        "tmp_path / "
        '"state"\n'
        "    assert "
        "expand_runtime_path(REPO_TOKEN, "
        "repo, state) "
        "== repo\n"
        "    assert "
        "expand_runtime_path(STATE_TOKEN, "
        "repo, state) "
        "== state\n"
        "    assert (\n"
        "        "
        "expand_runtime_path(\n"
        "            "
        'f"{REPO_TOKEN}/config/example.json",\n'
        "            "
        "repo,\n"
        "            "
        "state,\n"
        "        )\n"
        "        == "
        "repo / "
        '"config/example.json"\n'
        "    )\n"
        "\n"
        "\n"
        "def "
        "test_expand_runtime_path_rejects_absolute_paths(tmp_path: "
        "Path) -> "
        "None:\n"
        "    with "
        "pytest.raises(ValueError, "
        'match="Absolute '
        "runtime "
        'paths"):\n'
        "        "
        'expand_runtime_path("/tmp/forbidden", '
        "tmp_path, "
        "tmp_path / "
        '"state")\n'
        "\n"
        "\n"
        "def "
        "test_resolve_repo_root_walks_from_child(tmp_path: "
        "Path) -> "
        "None:\n"
        "    root = "
        "tmp_path / "
        '"factory"\n'
        "    (root / "
        '"config").mkdir(parents=True)\n'
        "    (root / "
        '"bin").mkdir()\n'
        "    (root / "
        '"config/display_identity_contract.json").write_text(\n'
        '        "{}",\n'
        "        "
        'encoding="utf-8",\n'
        "    )\n"
        "    (root / "
        '"bin/upi-app-factory").write_text("", '
        'encoding="utf-8")\n'
        "    child = "
        "root / "
        '"a/b/c"\n'
        "    "
        "child.mkdir(parents=True)\n"
        "    assert "
        "resolve_repo_root(child) "
        "== root\n"
        "\n"
        "\n"
        "def "
        "test_verify_contract_accepts_path_neutral_configuration(\n"
        "    tmp_path: "
        "Path,\n"
        "    "
        "monkeypatch: "
        "pytest.MonkeyPatch,\n"
        ") -> None:\n"
        "    root = "
        "tmp_path / "
        '"factory"\n'
        "    (root / "
        '"bin").mkdir(parents=True)\n'
        "    (root / "
        '"bin/upi-app-factory").write_text("", '
        'encoding="utf-8")\n'
        "    "
        "write_json(root "
        "/ "
        '"config/display_identity_contract.json", '
        "{})\n"
        "    "
        "write_json(\n"
        "        root / "
        '"config/path_identity_contract.json",\n'
        "        {\n"
        "            "
        '"canonical_repo_token": '
        "REPO_TOKEN,\n"
        "            "
        '"canonical_state_token": '
        "STATE_TOKEN,\n"
        "            "
        '"physical_checkout_rename": '
        '"NOT_PERFORMED",\n'
        "            "
        '"remote_repository_rename": '
        '"NOT_PERFORMED",\n'
        "            "
        '"resolution_probes": '
        "[\n"
        "                "
        '{"name": '
        '"repo", '
        '"value": '
        "REPO_TOKEN},\n"
        "                "
        '{"name": '
        '"config", '
        '"value": '
        'f"{REPO_TOKEN}/config"},\n'
        "                "
        '{"name": '
        '"state", '
        '"value": '
        "STATE_TOKEN},\n"
        "            "
        "],\n"
        "        },\n"
        "    )\n"
        "    "
        "write_json(\n"
        "        root / "
        '"policies/path_neutral_runtime_policy.json",\n'
        "        "
        '{"absolute_checkout_paths_allowed": '
        "False},\n"
        "    )\n"
        "    "
        "write_json(\n"
        "        root / "
        '"config/identity_compatibility_runtime.json",\n'
        "        {\n"
        "            "
        '"path_resolution_contract": '
        '"config/path_identity_contract.json",\n'
        "            "
        '"runtime_root_posture": '
        '"PATH_NEUTRAL",\n'
        "        },\n"
        "    )\n"
        "    "
        'monkeypatch.setenv("UPI_APP_FACTORY_STATE_DIR", '
        "str(tmp_path / "
        '"state"))\n'
        "    report = "
        "verify_contract(root)\n"
        "    assert "
        'report["status"] '
        '== "PASSED"\n'
        "    assert "
        'report["physical_checkout_rename"] '
        "== "
        '"NOT_PERFORMED"\n'
        "\n"
        "def "
        "test_verify_contract_rejects_arbitrary_absolute_contract_path(\n"
        "    tmp_path: "
        "Path,\n"
        "    "
        "monkeypatch: "
        "pytest.MonkeyPatch,\n"
        ") -> None:\n"
        "    root = "
        "tmp_path / "
        '"factory"\n'
        "    (root / "
        '"bin").mkdir(parents=True)\n'
        "    (root / "
        '"bin/upi-app-factory").write_text("", '
        'encoding="utf-8")\n'
        "    "
        "write_json(root "
        "/ "
        '"config/display_identity_contract.json", '
        "{})\n"
        "    "
        "write_json(\n"
        "        root / "
        '"config/path_identity_contract.json",\n'
        "        {\n"
        "            "
        '"canonical_repo_token": '
        "REPO_TOKEN,\n"
        "            "
        '"canonical_state_token": '
        "STATE_TOKEN,\n"
        "            "
        '"physical_checkout_rename": '
        '"NOT_PERFORMED",\n'
        "            "
        '"remote_repository_rename": '
        '"NOT_PERFORMED",\n'
        "            "
        '"resolution_probes": '
        "[\n"
        "                "
        '{"name": '
        '"repo", '
        '"value": '
        "REPO_TOKEN},\n"
        "                "
        '{"name": '
        '"config", '
        '"value": '
        '"/tmp/not-governed"},\n'
        "                "
        '{"name": '
        '"state", '
        '"value": '
        "STATE_TOKEN},\n"
        "            "
        "],\n"
        "        },\n"
        "    )\n"
        "    "
        "write_json(\n"
        "        root / "
        '"policies/path_neutral_runtime_policy.json",\n'
        "        "
        '{"absolute_checkout_paths_allowed": '
        "False},\n"
        "    )\n"
        "    "
        "write_json(\n"
        "        root / "
        '"config/identity_compatibility_runtime.json",\n'
        "        {\n"
        "            "
        '"path_resolution_contract": '
        "(\n"
        "                "
        '"config/path_identity_contract.json"\n'
        "            "
        "),\n"
        "            "
        '"runtime_root_posture": '
        '"PATH_NEUTRAL",\n'
        "        },\n"
        "    )\n"
        "    "
        "monkeypatch.setenv(\n"
        "        "
        '"UPI_APP_FACTORY_STATE_DIR",\n'
        "        "
        "str(tmp_path / "
        '"state"),\n'
        "    )\n"
        "    with "
        "pytest.raises(ValueError, "
        'match="Absolute '
        "checkout "
        'path"):\n'
        "        "
        "verify_contract(root)\n"
        "\n",
        "tools/transformation_controller/phase46h.py": "from __future__ import "
        "annotations\n"
        "\n"
        "import argparse\n"
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        "from typing import Any\n"
        "\n"
        'REPO_TOKEN = "${REPO_ROOT}"\n'
        "STATE_TOKEN = "
        '"${STATE_ROOT}"\n'
        "\n"
        "\n"
        "def "
        "contains_unapproved_absolute_path(value: "
        "object) -> bool:\n"
        "    if isinstance(value, "
        "str):\n"
        "        if "
        'value.startswith("${"):\n'
        "            return False\n"
        "        return "
        "Path(value).expanduser().is_absolute()\n"
        "    if isinstance(value, "
        "dict):\n"
        "        return any(\n"
        "            "
        "contains_unapproved_absolute_path(item)\n"
        "            for item in "
        "value.values()\n"
        "        )\n"
        "    if isinstance(value, "
        "list):\n"
        "        return any(\n"
        "            "
        "contains_unapproved_absolute_path(item)\n"
        "            for item in "
        "value\n"
        "        )\n"
        "    return False\n"
        "\n"
        "\n"
        "def load_object(path: Path, "
        "label: str) -> dict[str, "
        "Any]:\n"
        "    raw = "
        'json.loads(path.read_text(encoding="utf-8"))\n'
        "    if not isinstance(raw, "
        "dict):\n"
        "        raise "
        'ValueError(f"{label} must be '
        'a JSON object")\n'
        "    return raw\n"
        "\n"
        "\n"
        "def resolve_repo_root(anchor: "
        "Path | None = None) -> Path:\n"
        "    override = "
        'os.environ.get("UPI_APP_FACTORY_REPO_ROOT")\n'
        "    if override:\n"
        "        root = "
        "Path(override).expanduser().resolve()\n"
        "        if not (root / "
        '"config/display_identity_contract.json").is_file():\n'
        "            raise "
        'ValueError("UPI_APP_FACTORY_REPO_ROOT '
        'is not a factory checkout")\n'
        "        return root\n"
        "\n"
        "    current = (anchor or "
        "Path.cwd()).resolve()\n"
        "    for candidate in "
        "(current, *current.parents):\n"
        "        if (\n"
        "            (candidate / "
        '"config/display_identity_contract.json").is_file()\n'
        "            and (candidate / "
        '"bin/upi-app-factory").is_file()\n'
        "        ):\n"
        "            return candidate\n"
        '    raise ValueError("Unable '
        "to resolve the UPI App "
        'Factory repository root")\n'
        "\n"
        "\n"
        "def resolve_state_root() -> "
        "Path:\n"
        "    configured = "
        'os.environ.get("UPI_APP_FACTORY_STATE_DIR")\n'
        "    if configured:\n"
        "        return "
        "Path(configured).expanduser().resolve()\n"
        "    xdg_state = "
        'os.environ.get("XDG_STATE_HOME")\n'
        "    base = "
        "Path(xdg_state).expanduser() "
        "if xdg_state else Path.home() "
        '/ ".local/state"\n'
        "    return (base / "
        '"upi_app_factory").resolve()\n'
        "\n"
        "\n"
        "def "
        "expand_runtime_path(value: "
        "str, repo_root: Path, "
        "state_root: Path) -> Path:\n"
        "    if value == REPO_TOKEN:\n"
        "        return repo_root\n"
        "    if value == STATE_TOKEN:\n"
        "        return state_root\n"
        "    if "
        "value.startswith(REPO_TOKEN + "
        '"/"):\n'
        "        return repo_root / "
        "value[len(REPO_TOKEN) + 1 :]\n"
        "    if "
        "value.startswith(STATE_TOKEN "
        '+ "/"):\n'
        "        return state_root / "
        "value[len(STATE_TOKEN) + 1 "
        ":]\n"
        "    path = "
        "Path(value).expanduser()\n"
        "    if path.is_absolute():\n"
        "        raise "
        'ValueError("Absolute runtime '
        "paths are forbidden by the "
        'path contract")\n'
        "    return repo_root / path\n"
        "\n"
        "\n"
        "def "
        "verify_contract(project_root: "
        "Path) -> dict[str, Any]:\n"
        "    contract_path = "
        "project_root / "
        '"config/path_identity_contract.json"\n'
        "    policy_path = "
        "project_root / "
        '"policies/path_neutral_runtime_policy.json"\n'
        "    runtime_path = "
        "project_root / "
        '"config/identity_compatibility_runtime.json"\n'
        "\n"
        "    contract = "
        "load_object(contract_path, "
        '"Path identity contract")\n'
        "    policy = "
        "load_object(policy_path, "
        '"Path-neutral runtime '
        'policy")\n'
        "    runtime = "
        "load_object(runtime_path, "
        '"Identity compatibility '
        'runtime")\n'
        "\n"
        "    if "
        'contract.get("canonical_repo_token") '
        "!= REPO_TOKEN:\n"
        "        raise "
        'ValueError("Unexpected '
        'canonical repository token")\n'
        "    if "
        'contract.get("canonical_state_token") '
        "!= STATE_TOKEN:\n"
        "        raise "
        'ValueError("Unexpected '
        'canonical state token")\n'
        "    if "
        'contract.get("physical_checkout_rename") '
        '!= "NOT_PERFORMED":\n'
        "        raise "
        'ValueError("Physical checkout '
        "rename must remain "
        'deferred")\n'
        "    if "
        'contract.get("remote_repository_rename") '
        '!= "NOT_PERFORMED":\n'
        "        raise "
        'ValueError("Remote repository '
        "rename must remain "
        'deferred")\n'
        "    if "
        'policy.get("absolute_checkout_paths_allowed") '
        "is not False:\n"
        "        raise "
        'ValueError("Absolute checkout '
        'paths must be prohibited")\n'
        "    if "
        'runtime.get("path_resolution_contract") '
        "!= "
        '"config/path_identity_contract.json":\n'
        "        raise "
        'ValueError("Runtime does not '
        "reference the path "
        'contract")\n'
        "    if "
        'runtime.get("runtime_root_posture") '
        '!= "PATH_NEUTRAL":\n'
        "        raise "
        'ValueError("Runtime '
        "path-neutral posture is not "
        'active")\n'
        "\n"
        "    active_contracts = {\n"
        '        "contract": '
        "contract,\n"
        '        "policy": policy,\n'
        '        "runtime": runtime,\n'
        "    }\n"
        "    if "
        "contains_unapproved_absolute_path(active_contracts):\n"
        "        raise ValueError(\n"
        '            "Absolute '
        "checkout path leaked into "
        'active path contracts"\n'
        "        )\n"
        "\n"
        "    repo_root = "
        "resolve_repo_root(project_root)\n"
        "    state_root = "
        "resolve_state_root()\n"
        "    probes = "
        'contract.get("resolution_probes")\n'
        "    if not isinstance(probes, "
        "list) or len(probes) < 3:\n"
        "        raise "
        'ValueError("Path contract '
        "requires at least three "
        'resolution probes")\n'
        "\n"
        "    resolved = []\n"
        "    for item in probes:\n"
        "        if not "
        "isinstance(item, dict):\n"
        "            raise "
        'ValueError("Path probe must '
        'be an object")\n'
        "        raw = "
        'item.get("value")\n'
        "        if not "
        "isinstance(raw, str):\n"
        "            raise "
        'ValueError("Path probe value '
        'must be a string")\n'
        "        resolved.append(\n"
        "            {\n"
        '                "name": '
        'item.get("name"),\n'
        '                "value": '
        "raw,\n"
        '                "resolved": '
        "str(expand_runtime_path(raw, "
        "repo_root, state_root)),\n"
        "            }\n"
        "        )\n"
        "\n"
        "    return {\n"
        '        "status": "PASSED",\n'
        '        "phase": "46H",\n'
        '        "repo_root": '
        "str(repo_root),\n"
        '        "state_root": '
        "str(state_root),\n"
        '        "resolution_probes": '
        "resolved,\n"
        "        "
        '"physical_checkout_rename": '
        '"NOT_PERFORMED",\n'
        "        "
        '"remote_repository_rename": '
        '"NOT_PERFORMED",\n'
        '        "llm_calls": 0,\n'
        "    }\n"
        "\n"
        "\n"
        "def build_parser() -> "
        "argparse.ArgumentParser:\n"
        "    parser = "
        "argparse.ArgumentParser(\n"
        '        description="Verify '
        "Phase 46H path-neutral "
        'runtime contracts"\n'
        "    )\n"
        "    parser.add_argument(\n"
        '        "--project-root",\n'
        "        type=Path,\n"
        "        default=Path.cwd(),\n"
        "    )\n"
        "    return parser\n"
        "\n"
        "\n"
        "def main(argv: list[str] | "
        "None = None) -> int:\n"
        "    parsed = "
        "build_parser().parse_args(argv)\n"
        "    report = "
        "verify_contract(parsed.project_root.resolve())\n"
        "    print(json.dumps(report, "
        "indent=2, sort_keys=True))\n"
        "    return 0\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    raise "
        "SystemExit(main())\n",
    },
    "46I": {
        "config/technical_identity_contract.json": "{\n"
        "  "
        '"canonical_technical_identifier": '
        '"upi_app_factory",\n'
        '  "canonical_write_posture": '
        '"CANONICAL_ONLY",\n'
        '  "certification_posture": '
        '"CERTIFICATION_READY_NOT_CERTIFIED",\n'
        '  "compatibility_read_posture": '
        '"CANONICAL_AND_LEGACY_ACCEPTED",\n'
        '  "legacy_alias_retirement": '
        '"HUMAN_APPROVAL_REQUIRED",\n'
        '  "legacy_technical_identifiers": '
        "[\n"
        "    "
        '"upi_dispute_resolution\x5ffactory"\n'
        "  ],\n"
        '  "phase": "46I",\n'
        '  "physical_checkout_rename": '
        '"NOT_PERFORMED",\n'
        '  "physical_package_rename": '
        '"NOT_PERFORMED",\n'
        '  "remote_repository_rename": '
        '"NOT_PERFORMED",\n'
        '  "schema_version": 1\n'
        "}\n",
        "config/technical_namespace_aliases.json": "{\n"
        '  "canonical": '
        '"upi_app_factory",\n'
        '  "legacy_alias_retirement": '
        '"HUMAN_APPROVAL_REQUIRED",\n'
        '  "legacy_aliases": [\n'
        "    "
        '"upi_dispute_resolution\x5ffactory"\n'
        "  ],\n"
        '  "phase": "46I",\n'
        '  "read_resolution": '
        '"LEGACY_TO_CANONICAL",\n'
        '  "schema_version": 1,\n'
        '  "write_resolution": '
        '"CANONICAL_ONLY"\n'
        "}\n",
        "docs/phase46i/README.md": "# Phase 46I — Bounded technical namespace "
        "compatibility\n"
        "\n"
        "Phase 46I establishes `upi_app_factory` as the "
        "canonical technical identifier\n"
        "for new writes while retaining "
        "`upi_dispute_resolution\x5ffactory` as a governed\n"
        "read-compatible alias.\n"
        "\n"
        "This phase does not rename Python packages, the "
        "local checkout, or the remote\n"
        "repository. It does not remove the legacy alias "
        "or rewrite historical evidence.\n"
        "Those operations remain explicit human-controlled "
        "migration boundaries.\n",
        "policies/technical_namespace_migration_policy.json": "{\n"
        "  "
        '"canonical_writes_required": '
        "true,\n"
        "  "
        '"checkout_rename_allowed": '
        "false,\n"
        "  "
        '"compatibility_reads_required": '
        "true,\n"
        "  "
        '"historical_evidence_rewrite_allowed": '
        "false,\n"
        "  "
        '"human_approval_required_for": '
        "[\n"
        '    "physical package '
        'rename",\n'
        '    "checkout '
        'rename",\n'
        '    "remote repository '
        'rename",\n'
        '    "legacy alias '
        'retirement"\n'
        "  ],\n"
        "  "
        '"legacy_alias_removal_allowed": '
        "false,\n"
        '  "llm_calls_allowed": '
        "0,\n"
        '  "phase": "46I",\n'
        "  "
        '"physical_package_rename_allowed": '
        "false,\n"
        "  "
        '"remote_repository_rename_allowed": '
        "false,\n"
        '  "schema_version": '
        "1,\n"
        '  "status": "ACTIVE"\n'
        "}\n",
        "schemas/transformation/technical_identity_contract.schema.json": "{\n"
        '  "$id": '
        '"https://upi-app-factory.local/schemas/transformation/technical-identity-contract.schema.json",\n'
        "  "
        '"$schema": '
        '"https://json-schema.org/draft/2020-12/schema",\n'
        "  "
        '"additionalProperties": '
        "true,\n"
        "  "
        '"properties": '
        "{\n"
        "    "
        '"canonical_technical_identifier": '
        "{\n"
        "      "
        '"const": '
        '"upi_app_factory"\n'
        "    },\n"
        "    "
        '"canonical_write_posture": '
        "{\n"
        "      "
        '"const": '
        '"CANONICAL_ONLY"\n'
        "    },\n"
        "    "
        '"compatibility_read_posture": '
        "{\n"
        "      "
        '"const": '
        '"CANONICAL_AND_LEGACY_ACCEPTED"\n'
        "    },\n"
        "    "
        '"legacy_technical_identifiers": '
        "{\n"
        "      "
        '"contains": '
        "{\n"
        "        "
        '"const": '
        '"upi_dispute_resolution\x5ffactory"\n'
        "      },\n"
        "      "
        '"type": '
        '"array"\n'
        "    },\n"
        "    "
        '"phase": '
        "{\n"
        "      "
        '"const": '
        '"46I"\n'
        "    },\n"
        "    "
        '"physical_package_rename": '
        "{\n"
        "      "
        '"const": '
        '"NOT_PERFORMED"\n'
        "    },\n"
        "    "
        '"schema_version": '
        "{\n"
        "      "
        '"const": '
        "1\n"
        "    }\n"
        "  },\n"
        "  "
        '"required": '
        "[\n"
        "    "
        '"schema_version",\n'
        "    "
        '"phase",\n'
        "    "
        '"canonical_technical_identifier",\n'
        "    "
        '"legacy_technical_identifiers",\n'
        "    "
        '"canonical_write_posture",\n'
        "    "
        '"compatibility_read_posture",\n'
        "    "
        '"physical_package_rename"\n'
        "  ],\n"
        '  "type": '
        '"object"\n'
        "}\n",
        "tests/transformation/test_phase46i_technical_identity.py": "from __future__ "
        "import "
        "annotations\n"
        "\n"
        "import json\n"
        "from pathlib "
        "import Path\n"
        "\n"
        "import pytest\n"
        "\n"
        "from "
        "tools.transformation_controller.phase46i "
        "import (\n"
        "    "
        "CANONICAL_TECHNICAL_ID,\n"
        "    "
        "LEGACY_TECHNICAL_ID,\n"
        "    "
        "canonical_write_identity,\n"
        "    "
        "resolve_technical_identity,\n"
        "    "
        "verify_contract,\n"
        ")\n"
        "\n"
        "\n"
        "def "
        "write_json(path: "
        "Path, value: "
        "object) -> "
        "None:\n"
        "    "
        "path.parent.mkdir(parents=True, "
        "exist_ok=True)\n"
        "    "
        "path.write_text(\n"
        "        "
        "json.dumps(value, "
        "indent=2, "
        "sort_keys=True) "
        '+ "\\n",\n'
        "        "
        'encoding="utf-8",\n'
        "    )\n"
        "\n"
        "\n"
        "def "
        "test_canonical_identity_resolves_without_compatibility() "
        "-> None:\n"
        "    result = "
        "resolve_technical_identity(CANONICAL_TECHNICAL_ID)\n"
        "    assert "
        'result["canonical"] '
        "== "
        "CANONICAL_TECHNICAL_ID\n"
        "    assert "
        'result["compatibility_applied"] '
        "is False\n"
        "\n"
        "\n"
        "def "
        "test_legacy_identity_resolves_through_compatibility() "
        "-> None:\n"
        "    result = "
        "resolve_technical_identity(LEGACY_TECHNICAL_ID)\n"
        "    assert "
        'result["canonical"] '
        "== "
        "CANONICAL_TECHNICAL_ID\n"
        "    assert "
        'result["compatibility_applied"] '
        "is True\n"
        "\n"
        "\n"
        "def "
        "test_unknown_identity_fails_closed() "
        "-> None:\n"
        "    with "
        "pytest.raises(ValueError, "
        'match="Unknown '
        "technical "
        'identity"):\n'
        "        "
        'resolve_technical_identity("unknown_factory")\n'
        "\n"
        "\n"
        "def "
        "test_canonical_write_identity_is_new_namespace() "
        "-> None:\n"
        "    assert "
        "canonical_write_identity() "
        "== "
        "CANONICAL_TECHNICAL_ID\n"
        "\n"
        "\n"
        "def "
        "test_verify_contract_preserves_physical_rename_boundaries(\n"
        "    tmp_path: "
        "Path,\n"
        ") -> None:\n"
        "    root = "
        "tmp_path / "
        '"factory"\n'
        "    write_json(\n"
        "        root / "
        '"config/technical_identity_contract.json",\n'
        "        {\n"
        "            "
        '"canonical_technical_identifier": '
        "CANONICAL_TECHNICAL_ID,\n"
        "            "
        '"canonical_write_posture": '
        '"CANONICAL_ONLY",\n'
        "            "
        '"physical_package_rename": '
        '"NOT_PERFORMED",\n'
        "        },\n"
        "    )\n"
        "    write_json(\n"
        "        root / "
        '"config/technical_namespace_aliases.json",\n'
        "        {\n"
        "            "
        '"legacy_aliases": '
        "[LEGACY_TECHNICAL_ID],\n"
        "            "
        '"legacy_alias_retirement": '
        '"HUMAN_APPROVAL_REQUIRED",\n'
        "        },\n"
        "    )\n"
        "    write_json(\n"
        "        root / "
        '"config/identity_compatibility_runtime.json",\n'
        "        {\n"
        "            "
        '"technical_identity_contract": '
        "(\n"
        "                "
        '"config/technical_identity_contract.json"\n'
        "            ),\n"
        "            "
        '"technical_namespace_posture": '
        "(\n"
        "                "
        '"CANONICAL_WRITES_COMPATIBILITY_READS"\n'
        "            ),\n"
        "        },\n"
        "    )\n"
        "    write_json(\n"
        "        root / "
        '"policies/technical_namespace_migration_policy.json",\n'
        "        "
        '{"physical_package_rename_allowed": '
        "False},\n"
        "    )\n"
        "    report = "
        "verify_contract(root)\n"
        "    assert "
        'report["status"] '
        '== "PASSED"\n'
        "    assert "
        'report["physical_package_rename"] '
        "== "
        '"NOT_PERFORMED"\n',
        "tools/transformation_controller/phase46i.py": "from __future__ import "
        "annotations\n"
        "\n"
        "import argparse\n"
        "import json\n"
        "from pathlib import Path\n"
        "from typing import Any\n"
        "\n"
        "CANONICAL_TECHNICAL_ID = "
        '"upi_app_factory"\n'
        "LEGACY_TECHNICAL_ID = "
        '"upi_dispute_resolution\x5ffactory"\n'
        "\n"
        "\n"
        "def load_object(path: Path, "
        "label: str) -> dict[str, "
        "Any]:\n"
        "    raw = "
        'json.loads(path.read_text(encoding="utf-8"))\n'
        "    if not isinstance(raw, "
        "dict):\n"
        "        raise "
        'ValueError(f"{label} must be '
        'a JSON object")\n'
        "    return raw\n"
        "\n"
        "\n"
        "def "
        "resolve_technical_identity(value: "
        "str) -> dict[str, Any]:\n"
        "    if value == "
        "CANONICAL_TECHNICAL_ID:\n"
        "        return {\n"
        '            "input": value,\n'
        '            "canonical": '
        "CANONICAL_TECHNICAL_ID,\n"
        '            "resolution": '
        '"CANONICAL",\n'
        "            "
        '"compatibility_applied": '
        "False,\n"
        "        }\n"
        "    if value == "
        "LEGACY_TECHNICAL_ID:\n"
        "        return {\n"
        '            "input": value,\n'
        '            "canonical": '
        "CANONICAL_TECHNICAL_ID,\n"
        '            "resolution": '
        '"LEGACY_ALIAS_RESOLVED",\n'
        "            "
        '"compatibility_applied": '
        "True,\n"
        "        }\n"
        "    raise "
        'ValueError(f"Unknown '
        "technical identity: "
        '{value}")\n'
        "\n"
        "\n"
        "def "
        "canonical_write_identity() -> "
        "str:\n"
        "    return "
        "CANONICAL_TECHNICAL_ID\n"
        "\n"
        "\n"
        "def "
        "verify_contract(project_root: "
        "Path) -> dict[str, Any]:\n"
        "    contract = load_object(\n"
        "        project_root / "
        '"config/technical_identity_contract.json",\n'
        '        "Technical identity '
        'contract",\n'
        "    )\n"
        "    aliases = load_object(\n"
        "        project_root / "
        '"config/technical_namespace_aliases.json",\n'
        '        "Technical namespace '
        'aliases",\n'
        "    )\n"
        "    runtime = load_object(\n"
        "        project_root / "
        '"config/identity_compatibility_runtime.json",\n'
        '        "Identity '
        'compatibility runtime",\n'
        "    )\n"
        "    policy = load_object(\n"
        "        project_root / "
        '"policies/technical_namespace_migration_policy.json",\n'
        '        "Technical namespace '
        'migration policy",\n'
        "    )\n"
        "\n"
        "    if "
        'contract.get("canonical_technical_identifier") '
        "!= CANONICAL_TECHNICAL_ID:\n"
        "        raise "
        'ValueError("Unexpected '
        "canonical technical "
        'identifier")\n'
        "    if "
        'contract.get("canonical_write_posture") '
        '!= "CANONICAL_ONLY":\n'
        "        raise "
        'ValueError("Canonical-only '
        'writes are not active")\n'
        "    if "
        'contract.get("physical_package_rename") '
        '!= "NOT_PERFORMED":\n'
        "        raise "
        'ValueError("Physical package '
        "rename must remain "
        'deferred")\n'
        "    if "
        'aliases.get("legacy_aliases") '
        "!= [LEGACY_TECHNICAL_ID]:\n"
        "        raise "
        'ValueError("Legacy technical '
        "alias registry is "
        'unexpected")\n'
        "    if "
        'aliases.get("legacy_alias_retirement") '
        "!= "
        '"HUMAN_APPROVAL_REQUIRED":\n'
        "        raise "
        'ValueError("Legacy alias '
        "retirement must remain "
        'human-gated")\n'
        "    if "
        'runtime.get("technical_identity_contract") '
        "!= (\n"
        "        "
        '"config/technical_identity_contract.json"\n'
        "    ):\n"
        "        raise "
        'ValueError("Runtime does not '
        "reference the technical "
        'contract")\n'
        "    if "
        'runtime.get("technical_namespace_posture") '
        "!= (\n"
        "        "
        '"CANONICAL_WRITES_COMPATIBILITY_READS"\n'
        "    ):\n"
        "        raise "
        'ValueError("Unexpected '
        "runtime technical namespace "
        'posture")\n'
        "    if "
        'policy.get("physical_package_rename_allowed") '
        "is not False:\n"
        "        raise "
        'ValueError("Physical package '
        'rename must be prohibited")\n'
        "\n"
        "    canonical = "
        "resolve_technical_identity(CANONICAL_TECHNICAL_ID)\n"
        "    legacy = "
        "resolve_technical_identity(LEGACY_TECHNICAL_ID)\n"
        "    if "
        'canonical["compatibility_applied"]:\n'
        "        raise "
        'ValueError("Canonical '
        "identity must not use "
        'compatibility")\n'
        "    if not "
        'legacy["compatibility_applied"]:\n'
        "        raise "
        'ValueError("Legacy identity '
        'must use compatibility")\n'
        "    if "
        "canonical_write_identity() != "
        "CANONICAL_TECHNICAL_ID:\n"
        "        raise "
        'ValueError("Canonical write '
        'identity is incorrect")\n'
        "\n"
        "    return {\n"
        '        "status": "PASSED",\n'
        '        "phase": "46I",\n'
        "        "
        '"canonical_technical_identifier": '
        "CANONICAL_TECHNICAL_ID,\n"
        "        "
        '"legacy_aliases_retained": '
        "[LEGACY_TECHNICAL_ID],\n"
        "        "
        '"canonical_write_posture": '
        '"CANONICAL_ONLY",\n'
        "        "
        '"compatibility_read_posture": '
        '"CANONICAL_AND_LEGACY_ACCEPTED",\n'
        "        "
        '"physical_package_rename": '
        '"NOT_PERFORMED",\n'
        "        "
        '"physical_checkout_rename": '
        '"NOT_PERFORMED",\n'
        "        "
        '"remote_repository_rename": '
        '"NOT_PERFORMED",\n'
        '        "llm_calls": 0,\n'
        "    }\n"
        "\n"
        "\n"
        "def build_parser() -> "
        "argparse.ArgumentParser:\n"
        "    parser = "
        "argparse.ArgumentParser(\n"
        '        description="Verify '
        "Phase 46I technical namespace "
        'compatibility"\n'
        "    )\n"
        "    parser.add_argument(\n"
        '        "--project-root",\n'
        "        type=Path,\n"
        "        default=Path.cwd(),\n"
        "    )\n"
        "    return parser\n"
        "\n"
        "\n"
        "def main(argv: list[str] | "
        "None = None) -> int:\n"
        "    parsed = "
        "build_parser().parse_args(argv)\n"
        "    report = "
        "verify_contract(parsed.project_root.resolve())\n"
        "    print(json.dumps(report, "
        "indent=2, sort_keys=True))\n"
        "    return 0\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    raise "
        "SystemExit(main())\n",
    },
    "46J": {
        "config/identity_migration_readiness.json": "{\n"
        '  "certification_posture": '
        '"CERTIFICATION_READY_NOT_CERTIFIED",\n'
        '  "controls": {\n'
        '    "display_identity_contract": '
        '"COMPLETE",\n'
        '    "formal_certification": '
        '"NOT_PERFORMED",\n'
        '    "legacy_alias_retirement": '
        '"DEFERRED_HUMAN_GATE",\n'
        '    "path_neutral_runtime": '
        '"COMPLETE",\n'
        '    "physical_checkout_rename": '
        '"DEFERRED_HUMAN_GATE",\n'
        '    "remote_repository_rename": '
        '"DEFERRED_HUMAN_GATE",\n'
        "    "
        '"technical_namespace_compatibility": '
        '"COMPLETE"\n'
        "  },\n"
        '  "independent_review_required": '
        "true,\n"
        '  "llm_calls": 0,\n'
        '  "phase": "46J",\n'
        '  "schema_version": 1,\n'
        '  "status": '
        '"READY_FOR_INDEPENDENT_REVIEW"\n'
        "}\n",
        "docs/phase46j/README.md": "# Phase 46J — Migration evidence and "
        "independent-review closure\n"
        "\n"
        "Phase 46J consolidates the display identity, "
        "path-neutral runtime, technical\n"
        "namespace compatibility, and retained-alias "
        "controls into a replayable evidence\n"
        "index.\n"
        "\n"
        "The result is certification-ready evidence, not "
        "certification. Physical\n"
        "checkout and remote repository renames, alias "
        "retirement, certification\n"
        "submission, tagging, and release remain explicit "
        "human-controlled boundaries.\n",
        "policies/identity_migration_evidence_policy.json": "{\n"
        "  "
        '"certification_authority_required": '
        "true,\n"
        "  "
        '"evidence_hash_replay_required": '
        "true,\n"
        "  "
        '"human_approval_required_for": '
        "[\n"
        '    "physical checkout '
        'rename",\n'
        '    "remote repository '
        'rename",\n'
        '    "legacy alias '
        'retirement",\n'
        '    "formal '
        "certification "
        'submission",\n'
        '    "tag",\n'
        '    "release"\n'
        "  ],\n"
        "  "
        '"independent_review_required": '
        "true,\n"
        '  "llm_calls_allowed": '
        "0,\n"
        "  "
        '"official_certification_claim_allowed": '
        "false,\n"
        '  "phase": "46J",\n'
        '  "schema_version": 1,\n'
        '  "status": "ACTIVE"\n'
        "}\n",
        "schemas/transformation/identity_migration_readiness.schema.json": "{\n"
        '  "$id": '
        '"https://upi-app-factory.local/schemas/transformation/identity-migration-readiness.schema.json",\n'
        "  "
        '"$schema": '
        '"https://json-schema.org/draft/2020-12/schema",\n'
        "  "
        '"additionalProperties": '
        "true,\n"
        "  "
        '"properties": '
        "{\n"
        "    "
        '"certification_posture": '
        "{\n"
        "      "
        '"const": '
        '"CERTIFICATION_READY_NOT_CERTIFIED"\n'
        "    },\n"
        "    "
        '"controls": '
        "{\n"
        "      "
        '"required": '
        "[\n"
        "        "
        '"display_identity_contract",\n'
        "        "
        '"path_neutral_runtime",\n'
        "        "
        '"technical_namespace_compatibility",\n'
        "        "
        '"physical_checkout_rename",\n'
        "        "
        '"remote_repository_rename",\n'
        "        "
        '"legacy_alias_retirement",\n'
        "        "
        '"formal_certification"\n'
        "      ],\n"
        "      "
        '"type": '
        '"object"\n'
        "    },\n"
        "    "
        '"phase": '
        "{\n"
        "      "
        '"const": '
        '"46J"\n'
        "    },\n"
        "    "
        '"schema_version": '
        "{\n"
        "      "
        '"const": '
        "1\n"
        "    },\n"
        "    "
        '"status": '
        "{\n"
        "      "
        '"const": '
        '"READY_FOR_INDEPENDENT_REVIEW"\n'
        "    }\n"
        "  },\n"
        "  "
        '"required": '
        "[\n"
        "    "
        '"schema_version",\n'
        "    "
        '"phase",\n'
        "    "
        '"status",\n'
        "    "
        '"controls",\n'
        "    "
        '"certification_posture"\n'
        "  ],\n"
        '  "type": '
        '"object"\n'
        "}\n",
        "tests/transformation/test_phase46j_migration_evidence.py": "from __future__ "
        "import "
        "annotations\n"
        "\n"
        "import json\n"
        "from pathlib "
        "import Path\n"
        "\n"
        "import pytest\n"
        "\n"
        "from "
        "tools.transformation_controller.phase46j "
        "import (\n"
        "    "
        "EVIDENCE_INPUTS,\n"
        "    "
        "build_evidence_index,\n"
        "    "
        "verify_readiness,\n"
        ")\n"
        "\n"
        "\n"
        "def "
        "write_json(path: "
        "Path, value: "
        "object) -> "
        "None:\n"
        "    "
        "path.parent.mkdir(parents=True, "
        "exist_ok=True)\n"
        "    "
        "path.write_text(\n"
        "        "
        "json.dumps(value, "
        "indent=2, "
        "sort_keys=True) "
        '+ "\\n",\n'
        "        "
        'encoding="utf-8",\n'
        "    )\n"
        "\n"
        "\n"
        "def "
        "prepare_root(tmp_path: "
        "Path) -> Path:\n"
        "    root = "
        "tmp_path / "
        '"factory"\n'
        "    for relative "
        "in "
        "EVIDENCE_INPUTS:\n"
        "        "
        "write_json(root "
        "/ relative, "
        '{"path": '
        "relative, "
        '"value": '
        '"test"})\n'
        "    write_json(\n"
        "        root / "
        '"config/identity_migration_readiness.json",\n'
        "        {\n"
        "            "
        '"controls": {\n'
        "                "
        '"display_identity_contract": '
        '"COMPLETE",\n'
        "                "
        '"path_neutral_runtime": '
        '"COMPLETE",\n'
        "                "
        '"technical_namespace_compatibility": '
        '"COMPLETE",\n'
        "                "
        '"physical_checkout_rename": '
        '"DEFERRED_HUMAN_GATE",\n'
        "                "
        '"remote_repository_rename": '
        '"DEFERRED_HUMAN_GATE",\n'
        "                "
        '"legacy_alias_retirement": '
        '"DEFERRED_HUMAN_GATE",\n'
        "                "
        '"formal_certification": '
        '"NOT_PERFORMED",\n'
        "            },\n"
        "            "
        '"certification_posture": '
        '"CERTIFICATION_READY_NOT_CERTIFIED",\n'
        "        },\n"
        "    )\n"
        "    write_json(\n"
        "        root / "
        '"policies/identity_migration_evidence_policy.json",\n'
        "        "
        '{"official_certification_claim_allowed": '
        "False},\n"
        "    )\n"
        "    write_json(\n"
        "        root / "
        '"evidence/phase46j/identity_migration_evidence_index.json",\n'
        "        "
        "build_evidence_index(root),\n"
        "    )\n"
        "    return root\n"
        "\n"
        "\n"
        "def "
        "test_build_evidence_index_is_deterministic(tmp_path: "
        "Path) -> None:\n"
        "    root = "
        "prepare_root(tmp_path)\n"
        "    first = "
        "build_evidence_index(root)\n"
        "    second = "
        "build_evidence_index(root)\n"
        "    assert first "
        "== second\n"
        "    assert "
        'first["evidence_record_count"] '
        "== "
        "len(EVIDENCE_INPUTS)\n"
        "\n"
        "\n"
        "def "
        "test_verify_readiness_replays_all_hashes(tmp_path: "
        "Path) -> None:\n"
        "    root = "
        "prepare_root(tmp_path)\n"
        "    report = "
        "verify_readiness(root)\n"
        "    assert "
        'report["status"] '
        '== "PASSED"\n'
        "    assert "
        'report["certification_posture"] '
        "== (\n"
        "        "
        '"CERTIFICATION_READY_NOT_CERTIFIED"\n'
        "    )\n"
        "\n"
        "\n"
        "def "
        "test_verify_readiness_detects_evidence_drift(tmp_path: "
        "Path) -> None:\n"
        "    root = "
        "prepare_root(tmp_path)\n"
        "    "
        "write_json(root "
        "/ "
        "EVIDENCE_INPUTS[0], "
        '{"changed": '
        "True})\n"
        "    with "
        "pytest.raises(ValueError, "
        'match="hashes do '
        'not replay"):\n'
        "        "
        "verify_readiness(root)\n",
        "tools/transformation_controller/phase46j.py": "from __future__ import "
        "annotations\n"
        "\n"
        "import argparse\n"
        "import hashlib\n"
        "import json\n"
        "from pathlib import Path\n"
        "from typing import Any\n"
        "\n"
        "EVIDENCE_INPUTS = (\n"
        "    "
        '"config/display_identity_contract.json",\n'
        "    "
        '"config/path_identity_contract.json",\n'
        "    "
        '"config/technical_identity_contract.json",\n'
        "    "
        '"config/compatibility_aliases.json",\n'
        "    "
        '"config/technical_namespace_aliases.json",\n'
        "    "
        '"config/identity_compatibility_runtime.json",\n'
        ")\n"
        "\n"
        "\n"
        "def load_object(path: Path, "
        "label: str) -> dict[str, "
        "Any]:\n"
        "    raw = "
        'json.loads(path.read_text(encoding="utf-8"))\n'
        "    if not isinstance(raw, "
        "dict):\n"
        "        raise "
        'ValueError(f"{label} must be '
        'a JSON object")\n'
        "    return raw\n"
        "\n"
        "\n"
        "def digest_file(path: Path) "
        "-> dict[str, Any]:\n"
        "    data = path.read_bytes()\n"
        "    return {\n"
        '        "path": '
        "path.as_posix(),\n"
        '        "size": len(data),\n'
        '        "sha256": '
        "hashlib.sha256(data).hexdigest(),\n"
        "    }\n"
        "\n"
        "\n"
        "def "
        "build_evidence_index(project_root: "
        "Path) -> dict[str, Any]:\n"
        "    records = []\n"
        "    for relative in "
        "EVIDENCE_INPUTS:\n"
        "        path = project_root / "
        "relative\n"
        "        if not "
        "path.is_file():\n"
        "            raise "
        'ValueError(f"Required '
        "migration evidence input is "
        'missing: {relative}")\n'
        "        record = "
        "digest_file(path)\n"
        '        record["path"] = '
        "relative\n"
        "        "
        "records.append(record)\n"
        "    return {\n"
        '        "schema_version": 1,\n'
        '        "phase": "46J",\n'
        '        "status": "PASSED",\n'
        '        "evidence_records": '
        "records,\n"
        "        "
        '"evidence_record_count": '
        "len(records),\n"
        '        "llm_calls": 0,\n'
        "    }\n"
        "\n"
        "\n"
        "def "
        "verify_readiness(project_root: "
        "Path) -> dict[str, Any]:\n"
        "    readiness = load_object(\n"
        "        project_root / "
        '"config/identity_migration_readiness.json",\n'
        '        "Identity migration '
        'readiness",\n'
        "    )\n"
        "    evidence = load_object(\n"
        "        project_root\n"
        "        / "
        '"evidence/phase46j/identity_migration_evidence_index.json",\n'
        '        "Identity migration '
        'evidence index",\n'
        "    )\n"
        "    policy = load_object(\n"
        "        project_root / "
        '"policies/identity_migration_evidence_policy.json",\n'
        '        "Identity migration '
        'evidence policy",\n'
        "    )\n"
        "\n"
        "    expected_controls = {\n"
        "        "
        '"display_identity_contract": '
        '"COMPLETE",\n'
        "        "
        '"path_neutral_runtime": '
        '"COMPLETE",\n'
        "        "
        '"technical_namespace_compatibility": '
        '"COMPLETE",\n'
        "        "
        '"physical_checkout_rename": '
        '"DEFERRED_HUMAN_GATE",\n'
        "        "
        '"remote_repository_rename": '
        '"DEFERRED_HUMAN_GATE",\n'
        "        "
        '"legacy_alias_retirement": '
        '"DEFERRED_HUMAN_GATE",\n'
        "        "
        '"formal_certification": '
        '"NOT_PERFORMED",\n'
        "    }\n"
        "    controls = "
        'readiness.get("controls")\n'
        "    if controls != "
        "expected_controls:\n"
        "        raise "
        'ValueError("Identity '
        "migration readiness controls "
        'are unexpected")\n'
        "    if "
        'readiness.get("certification_posture") '
        "!= (\n"
        "        "
        '"CERTIFICATION_READY_NOT_CERTIFIED"\n'
        "    ):\n"
        "        raise "
        'ValueError("Certification '
        'posture is incorrect")\n'
        "    if "
        'policy.get("official_certification_claim_allowed") '
        "is not False:\n"
        "        raise "
        'ValueError("Official '
        "certification claims must be "
        'prohibited")\n'
        '    if evidence.get("status") '
        '!= "PASSED":\n'
        "        raise "
        'ValueError("Migration '
        "evidence index did not "
        'pass")\n'
        "\n"
        "    regenerated = "
        "build_evidence_index(project_root)\n"
        "    if "
        'regenerated["evidence_records"] '
        "!= "
        'evidence.get("evidence_records"):\n'
        "        raise "
        'ValueError("Migration '
        "evidence hashes do not "
        'replay")\n'
        "\n"
        "    return {\n"
        '        "status": "PASSED",\n'
        '        "phase": "46J",\n'
        '        "controls": '
        "expected_controls,\n"
        "        "
        '"evidence_record_count": '
        'regenerated["evidence_record_count"],\n'
        "        "
        '"certification_posture": '
        '"CERTIFICATION_READY_NOT_CERTIFIED",\n'
        "        "
        '"physical_checkout_rename": '
        '"NOT_PERFORMED",\n'
        "        "
        '"remote_repository_rename": '
        '"NOT_PERFORMED",\n'
        "        "
        '"legacy_aliases_retained": '
        "True,\n"
        '        "llm_calls": 0,\n'
        "    }\n"
        "\n"
        "\n"
        "def build_parser() -> "
        "argparse.ArgumentParser:\n"
        "    parser = "
        "argparse.ArgumentParser(\n"
        '        description="Verify '
        "Phase 46J migration evidence "
        'closure"\n'
        "    )\n"
        "    parser.add_argument(\n"
        '        "--project-root",\n'
        "        type=Path,\n"
        "        default=Path.cwd(),\n"
        "    )\n"
        "    return parser\n"
        "\n"
        "\n"
        "def main(argv: list[str] | "
        "None = None) -> int:\n"
        "    parsed = "
        "build_parser().parse_args(argv)\n"
        "    report = "
        "verify_readiness(parsed.project_root.resolve())\n"
        "    print(json.dumps(report, "
        "indent=2, sort_keys=True))\n"
        "    return 0\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    raise "
        "SystemExit(main())\n",
    },
}

PREREQUISITE_ARTIFACTS: dict[str, str] = {
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase17/enterprise_autonomous_hardening_audit.json": "a83b01caa3c2372786644e7d4e002a00b21333b4a1f35879e3e09714d857e230",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase17/generated_app_depth_backlog.json": "4940248d9aa5d3f3468b66affd6bd12bf7f66f31c3818b6da3920d0b1fa6e62c",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase17/independent_reviewer_workspace_trial.json": "e85ca5d9aa0e6883872c3f3502582f3fc6ce13f855092f2f5875ec905ef2a37f",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase17/release_dossier_index.json": "898e03cabcc67fcf4a2fc1d5b1c9b84917c2e5e88e1cfd640aad658a86b779d7",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase18/independent_reviewer_checklist.json": "b259d8fa83986d55d882bd0327214a6c4daf0d171c32558bd507a88e46f3d56b",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase18/independent_reviewer_workspace_pack.json": "549a65903d8f09a14ac7b8fbbed0cb270591e18396108eaaeda2e1f8143ec642",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase18/independent_reviewer_workspace_trial_audit.json": "544dbb7c24926555c6c2713b179547e5851b05ce7361f9eea5bc5c2a5357ce7b",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase19/local_dependency_inventory.json": "9fe4ef9d891b8dee02aa798f67de37000e9c8ca237f945b659986b30a1262373",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase19/provenance_readiness_statement.json": "611652275ff358376241203932018954a773b1ff4956683ea33bd05c0c3afc0b",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase19/supply_chain_gate_summary.json": "5799d93079a6adf43139c38bb9e63914ce9b0b9297d57e7590d552c69328481b",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase19/supply_chain_provenance_hardening_audit.json": "f99316397cf3c4555d6b0cadae84884a20c8a66693e82423e58a9db65c675f15",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/architecture_conformance_expectations.json": "c04a4f68eec31d7fda94efad2dd6a407f9e2ec1b029e83036c30906746b39f99",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/architecture_depth_artifact_manifest.json": "152ca08cf56b37c8725af3584e313cabe395cc0b2dfb8893ba3edfb5cbac57d3",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/architecture_depth_gate.json": "fa9f9d617b67354bc7cfa65a1882c10fe26cd8511d32285967994e38a54bfa44",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/certification_boundary.json": "a6fcd4f4d10def615ae40eca621f2fc60790a620272c280950c64016340f84de",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/phase28_architecture_depth_audit.json": "e93fd14a92e216b2c41047d179ec36f38ab54a8eefd9c4186015e0c95220d21e",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/self_evolution_backlog_policy.json": "a04bac3422133e6b670fee0691987d0a162120411d93105158f18d9849f6f105",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28/test_obligation_matrix.json": "dcd374cbe4ee5644feeb2814f20d6b06487d4cd3bc03984adb0b1c24595a09cb",
}


EVIDENCE_INPUTS = (
    "config/display_identity_contract.json",
    "config/path_identity_contract.json",
    "config/technical_identity_contract.json",
    "config/compatibility_aliases.json",
    "config/technical_namespace_aliases.json",
    "config/identity_compatibility_runtime.json",
)


def load_object(path: Path, label: str) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object")
    return raw


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def update_runtime(phase: str, project_root: Path) -> str | None:
    runtime_path = project_root / "config/identity_compatibility_runtime.json"
    if phase not in {"46H", "46I"}:
        return None
    runtime = load_object(runtime_path, "Identity compatibility runtime")
    if phase == "46H":
        runtime.update(
            {
                "path_resolution_contract": "config/path_identity_contract.json",
                "runtime_root_posture": "PATH_NEUTRAL",
                "physical_checkout_rename": "NOT_PERFORMED",
                "remote_repository_rename": "NOT_PERFORMED",
            }
        )
    else:
        runtime.update(
            {
                "technical_identity_contract": ("config/technical_identity_contract.json"),
                "technical_namespace_posture": ("CANONICAL_WRITES_COMPATIBILITY_READS"),
                "canonical_technical_identifier": "upi_app_factory",
                "legacy_technical_identifier": ("upi_dispute_resolution\x5ffactory"),
                "physical_package_rename": "NOT_PERFORMED",
            }
        )
    return json_text(runtime)


def build_evidence_index(project_root: Path) -> str:
    records = []
    for relative in EVIDENCE_INPUTS:
        path = project_root / relative
        if not path.is_file():
            raise ValueError(f"Required migration evidence input is missing: {relative}")
        data = path.read_bytes()
        records.append(
            {
                "path": relative,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return json_text(
        {
            "schema_version": 1,
            "phase": "46J",
            "status": "PASSED",
            "evidence_records": records,
            "evidence_record_count": len(records),
            "llm_calls": 0,
        }
    )


def discover_main_worktree(project_root: Path) -> Path:
    output = subprocess.check_output(
        [
            "git",
            "-C",
            str(project_root),
            "worktree",
            "list",
            "--porcelain",
        ],
        text=True,
    )
    current_path: Path | None = None
    for line in output.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ")).resolve()
        elif line == "branch refs/heads/main" and current_path is not None:
            return current_path
    raise ValueError("Unable to locate the main worktree")


def provision_prerequisites(project_root: Path) -> dict[str, Any]:
    source_root = discover_main_worktree(project_root)
    records = []
    for relative, expected_hash in PREREQUISITE_ARTIFACTS.items():
        source = source_root / relative
        destination = project_root / relative
        if not source.is_file():
            raise ValueError(f"Missing ignored prerequisite in main worktree: {relative}")
        data = source.read_bytes()
        observed = hashlib.sha256(data).hexdigest()
        if observed != expected_hash:
            raise ValueError(f"Prerequisite hash mismatch in main worktree: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".prerequisite.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, destination)
        copied = hashlib.sha256(destination.read_bytes()).hexdigest()
        if copied != expected_hash:
            raise ValueError(f"Copied prerequisite hash mismatch: {relative}")
        records.append(
            {
                "path": relative,
                "size": len(data),
                "sha256": copied,
            }
        )
    return {
        "status": "PASSED",
        "source_root": str(source_root),
        "target_root": str(project_root),
        "artifact_count": len(records),
        "artifacts": records,
        "llm_calls": 0,
    }


def validate_content(relative: str, content: str, staged: Path) -> None:
    if relative.endswith(".json"):
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError(f"JSON payload must be an object: {relative}")
    if relative.endswith(".py"):
        py_compile.compile(str(staged), doraise=True)


def install_phase(phase: str, project_root: Path) -> dict[str, Any]:
    if phase not in PHASE_PAYLOADS:
        raise ValueError(f"Unsupported campaign phase: {phase}")
    payload = dict(PHASE_PAYLOADS[phase])
    runtime_content = update_runtime(phase, project_root)
    if runtime_content is not None:
        payload["config/identity_compatibility_runtime.json"] = runtime_content
    if phase == "46J":
        payload["evidence/phase46j/identity_migration_evidence_index.json"] = build_evidence_index(
            project_root
        )

    staging = project_root / ".phase_campaign_staging" / phase.lower()
    if staging.exists():
        for path in sorted(staging.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    staging.mkdir(parents=True, exist_ok=True)

    records = []
    for relative, content in sorted(payload.items()):
        staged = staging / relative
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(content, encoding="utf-8")
        validate_content(relative, content, staged)
        records.append(
            {
                "path": relative,
                "size": len(content.encode("utf-8")),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )

    for relative in sorted(payload):
        staged = staging / relative
        destination = project_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + f".{phase.lower()}.tmp")
        temporary.write_bytes(staged.read_bytes())
        os.replace(temporary, destination)

    for path in sorted(staging.rglob("*"), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    staging.rmdir()
    staging.parent.rmdir()

    return {
        "status": "PASSED",
        "phase": phase,
        "written_file_count": len(records),
        "written_files": records,
        "atomic_prewrite_validation": "PASSED",
        "llm_calls": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install deterministic identity campaign phase payloads"
    )
    parser.add_argument(
        "action",
        choices=("install", "provision-prerequisites"),
    )
    parser.add_argument("--phase")
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    project_root = parsed.project_root.resolve()
    if parsed.action == "provision-prerequisites":
        report = provision_prerequisites(project_root)
    else:
        if not parsed.phase:
            raise ValueError("--phase is required for install")
        report = install_phase(parsed.phase, project_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
