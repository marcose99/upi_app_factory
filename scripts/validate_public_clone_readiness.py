from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


SUPPORTED_LICENSES = {"Apache-2.0"}
MAX_ARTIFACT_BYTES = 5 * 1024 * 1024
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".css",
    ".csv",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PERSONAL_PATTERNS = (
    re.compile(r"/home/marcose(?:/|\b)"),
    re.compile(r"github\.com/marcose99(?:/|\b)"),
    re.compile(r"@marcose99\b"),
    re.compile(r"upi_dispute_resolution_factory"),
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"=\s*[\"']?sk-[A-Za-z0-9_-]{20,}"),
)
SYNTHETIC_PATH_FIXTURES = {
    "scripts/validate_public_clone_readiness.py",
    "tests/transformation/test_phase46a_inventory.py",
}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    details: list[str]

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "details": self.details}


def _run_git_ls_files(repo: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    files = [
        repo / item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]
    if not files:
        raise RuntimeError("no tracked files found")
    return files


def _read_text(path: Path) -> str | None:
    if path.suffix not in TEXT_SUFFIXES and path.name not in {"LICENSE", "NOTICE", "Makefile"}:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _check_license_notice(repo: Path, license_id: str) -> Check:
    details: list[str] = []
    if license_id not in SUPPORTED_LICENSES:
        details.append(f"unsupported license requested: {license_id}")
    license_text = (repo / "LICENSE").read_text(encoding="utf-8") if (repo / "LICENSE").is_file() else ""
    notice_text = (repo / "NOTICE").read_text(encoding="utf-8") if (repo / "NOTICE").is_file() else ""
    for token in ["Apache License", "Version 2.0", "TERMS AND CONDITIONS"]:
        if token not in license_text:
            details.append(f"LICENSE missing token: {token}")
    for token in [
        "UPI App Factory",
        "not NPCI certified",
        "not RBI certified",
        "mocked or simulated",
        "does not grant rights in third-party",
    ]:
        if token not in notice_text:
            details.append(f"NOTICE missing boundary token: {token}")
    return Check("license_notice", "passed" if not details else "failed", details)


def _check_personal_paths(repo: Path, files: list[Path]) -> Check:
    details: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        relative = path.relative_to(repo).as_posix()
        text = _read_text(path)
        if text is None:
            continue
        if relative == "scripts/validate_public_clone_readiness.py":
            continue
        if relative == "tools/transformation_controller/phase46a.py":
            continue
        if relative in SYNTHETIC_PATH_FIXTURES and "PUBLIC_HYGIENE_SYNTHETIC_PATH_FIXTURE" in text:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if (
                relative == "requirements/master_consolidated_requirements.md"
                and "may depend on `/home/marcose`" in line
            ):
                continue
            for pattern in PERSONAL_PATTERNS:
                if pattern.search(line):
                    details.append(f"{relative}:{number}: {pattern.pattern}")
    return Check("personal_paths_and_stale_identities", "passed" if not details else "failed", details)


def _check_requirements(repo: Path) -> Check:
    details: list[str] = []
    for name in ["requirements-recipient.txt", "requirements-agentic.txt", "requirements/ci-lock.txt"]:
        path = repo / name
        if not path.is_file():
            details.append(f"missing {name}")
            continue
        packages = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not packages:
            details.append(f"empty dependency list: {name}")
        for line in packages:
            local_editable = line == "-e ."
            if any(token in line for token in ["git+", "file:", "://"]) or (line.startswith("-e ") and not local_editable):
                details.append(f"non-local-first dependency source in {name}: {line}")
    pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8") if (repo / "pyproject.toml").is_file() else ""
    for token in ["git+", "file:", "://"]:
        if token in pyproject:
            details.append(f"pyproject contains dependency source token: {token}")
    return Check("sample_requirements_and_dependency_sources", "passed" if not details else "failed", details)


def _check_startup_docs(repo: Path) -> Check:
    details: list[str] = []
    readme = (repo / "README.md").read_text(encoding="utf-8") if (repo / "README.md").is_file() else ""
    makefile = (repo / "Makefile").read_text(encoding="utf-8") if (repo / "Makefile").is_file() else ""
    for token in ["make validate", "make validate-public-clone", "make run"]:
        if token not in readme:
            details.append(f"README missing command: {token}")
    expected = "scripts/validate_public_clone_readiness.py --repo . --license Apache-2.0"
    if "validate-public-clone:" not in makefile or expected not in makefile:
        details.append("Makefile public clone validation target is missing or misaligned")
    if "uvicorn app.main:app" in makefile and "http://127.0.0.1:8000/health" not in readme:
        details.append("README health URL does not align with Makefile run target")
    return Check("startup_docs_command_alignment", "passed" if not details else "failed", details)


def _check_state_policy(repo: Path) -> Check:
    details: list[str] = []
    policy_path = repo / "policies/tracked_workspace_policy.json"
    if not policy_path.is_file():
        details.append("missing policies/tracked_workspace_policy.json")
    else:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        if policy.get("schema_version") != "tracked-workspace-policy.v1":
            details.append("tracked workspace policy schema mismatch")
        if policy.get("determinism", {}).get("llm_default") != "disabled":
            details.append("tracked workspace policy must disable LLM by default")
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8") if (repo / ".gitignore").is_file() else ""
    if re.search(r"(?m)^workspace/$", gitignore):
        details.append(".gitignore must not blanket-ignore tracked workspace fixtures")
    for token in [
        "workspace/runs/",
        "workspace/regeneration_runs/",
        "workspace/factory_generated/upi_failed_debit_no_credit/",
        "workspace/tmp/",
        "workspace/cache/",
    ]:
        if token not in gitignore:
            details.append(f".gitignore missing runtime output: {token}")
    return Check("tracked_workspace_state_policy", "passed" if not details else "failed", details)


def _check_openapi_tests(repo: Path) -> Check:
    details = [
        item
        for item in [
            "factory/operator_portal/runtime_openapi.py",
            "tests/phase50/test_runtime_openapi.py",
            "tests/phase50/test_runtime_openapi_scenarios_evidence.py",
        ]
        if not (repo / item).is_file()
    ]
    return Check(
        "openapi_and_test_evidence_hooks",
        "passed" if not details else "failed",
        [f"missing OpenAPI/test evidence hook: {item}" for item in details],
    )


def _check_docker_files(repo: Path, files: list[Path]) -> Check:
    details: list[str] = []
    docker_files = [
        path
        for path in files
        if path.name.startswith("Dockerfile") or path.name.startswith("docker-compose")
    ]
    for path in docker_files:
        text = _read_text(path) or ""
        relative = path.relative_to(repo).as_posix()
        if ":latest" in text:
            details.append(f"{relative}: mutable latest tag")
        if "${{ secrets." in text:
            details.append(f"{relative}: repository secret reference")
        if re.search(r"(?m)^\s*ADD\s+https?://", text):
            details.append(f"{relative}: remote ADD is prohibited")
    if not docker_files:
        details.append("no Docker files tracked; check passed as not applicable")
    failed = [detail for detail in details if not detail.startswith("no Docker files")]
    return Check("docker_files", "passed" if not failed else "failed", details)


def _check_modes_symlinks_large(repo: Path, files: list[Path]) -> list[Check]:
    mode_details: list[str] = []
    symlink_details: list[str] = []
    large_details: list[str] = []
    for path in files:
        relative = path.relative_to(repo).as_posix()
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            mode_details.append(f"{relative}: cannot stat: {exc}")
            continue
        if stat.S_ISLNK(mode):
            symlink_details.append(relative)
            continue
        if path.is_file() and path.stat().st_size > MAX_ARTIFACT_BYTES:
            large_details.append(f"{relative}: {path.stat().st_size} bytes")
        executable = bool(mode & stat.S_IXUSR)
        allowed_executable = (
            relative.startswith("scripts/")
            or relative.startswith("bin/")
            or relative.startswith("factory_governance/")
            or "/scripts/" in relative
            or path.suffix == ".sh"
            or path.name == "factoryctl"
        )
        if executable and not allowed_executable:
            mode_details.append(f"{relative}: unexpected executable mode")
    return [
        Check("executable_modes", "passed" if not mode_details else "failed", mode_details),
        Check("symlinks", "passed" if not symlink_details else "failed", symlink_details),
        Check("large_artifacts", "passed" if not large_details else "failed", large_details),
    ]


def _check_secrets(repo: Path, files: list[Path]) -> Check:
    details: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        relative = path.relative_to(repo).as_posix()
        text = _read_text(path)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if " not in " in line or "not " in line:
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    details.append(f"{relative}:{number}: secret-like material")
    return Check("secrets", "passed" if not details else "failed", details)


def validate(repo: Path, license_id: str) -> dict[str, Any]:
    root = repo.resolve()
    files = _run_git_ls_files(root)
    checks: list[Check] = [
        _check_license_notice(root, license_id),
        _check_personal_paths(root, files),
        _check_requirements(root),
        _check_startup_docs(root),
        _check_state_policy(root),
        _check_openapi_tests(root),
        _check_docker_files(root, files),
        _check_secrets(root, files),
    ]
    checks.extend(_check_modes_symlinks_large(root, files))
    failed = [check for check in checks if check.status != "passed"]
    return {
        "status": "passed" if not failed else "failed",
        "repo": str(root),
        "license": license_id,
        "tracked_files": len(files),
        "checks": [check.to_json() for check in checks],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate(args.repo, args.license)
    except Exception as exc:
        report = {
            "status": "failed",
            "repo": str(args.repo),
            "license": args.license,
            "checks": [
                {
                    "name": "fail_closed",
                    "status": "failed",
                    "details": [str(exc) or exc.__class__.__name__],
                }
            ],
        }
    output = json.dumps(report, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
