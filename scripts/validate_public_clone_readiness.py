from __future__ import annotations

import argparse
from dataclasses import dataclass
import io
import json
import math
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
    re.compile(
        r"-----BEGIN (?:(?:RSA|EC|OPENSSH|DSA|ENCRYPTED) )?PRIVATE KEY-----"
    ),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{32,}\b"),
    re.compile(r"=\s*[\"']?sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)\b(?:password|passwd|secret|client_secret|access_key|api_key)\b"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9_+/=-]{16,}"
    ),
    re.compile(
        r"(?i)\b(?:auth_token|access_token|api_token|token)\b"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9_+/=-]{32,}"
    ),
)
# Provider-neutral credentials are detected by the conjunction of an explicit
# secret-bearing context and a high-entropy value.  This complements the small
# set of formats for providers referenced by this repository without pretending
# to enumerate every vendor token prefix.
SECRET_CONTEXT = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9])"
    r"(?:api[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|"
    r"refresh[_-]?token|password|passwd|credential|private[_-]?key)"
    r"\s*[:=]\s*[\"']?([A-Za-z0-9_+/=.-]{20,})"
)
URI_CREDENTIAL = re.compile(
    r"(?i)\b(?:https?|postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://"
    r"[^\s/:@]{1,128}:([^\s/@]{12,})@"
)
SYNTHETIC_PATH_FIXTURES = {
    "scripts/validate_public_clone_readiness.py",
    "tests/transformation/test_phase46a_inventory.py",
}
SYNTHETIC_SECRET_FIXTURES = {
    "tests/test_portal_synthetic_data_contract.py": {
        'secret = "Build local disputes only. api_key=' + 'abcdefghijklmnopqrstuvwxyz123456"'
    },
    "tests/test_phase31_deep_generated_application_export_download_center.py": {
        'assert "-----BEGIN ' + 'PRIVATE KEY-----" not in text'
    },
    "tests/test_phase32_operator_portal_download_center.py": {
        'assert "-----BEGIN ' + 'PRIVATE KEY-----" not in service_source'
    },
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
            # Test-generated tracked fixtures may be absent from the current
            # worktree after an isolation cleanup.  They remain cloneable when
            # their index blob exists, so validate that authority rather than
            # treating transient worktree absence as a public-clone defect.
            indexed = subprocess.run(
                ["git", "-C", str(repo), "cat-file", "-e", f":{relative}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if indexed.returncode != 0:
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


def _reachable_blob_bytes(repo: Path) -> list[tuple[str, tuple[str, ...], bytes]]:
    objects = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--objects", "--all"],
        check=False,
        capture_output=True,
    )
    if objects.returncode != 0:
        raise RuntimeError(objects.stderr.decode(errors="replace").strip())
    paths_by_object: dict[bytes, set[str]] = {}
    for line in objects.stdout.splitlines():
        if not line:
            continue
        fields = line.split(maxsplit=1)
        paths_by_object.setdefault(fields[0], set())
        if len(fields) == 2:
            paths_by_object[fields[0]].add(fields[1].decode("utf-8", errors="replace"))
    object_ids = sorted(paths_by_object)
    if not object_ids:
        return []
    batch = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=b"\n".join(object_ids) + b"\n",
        check=False,
        capture_output=True,
    )
    if batch.returncode != 0:
        raise RuntimeError(batch.stderr.decode(errors="replace").strip())
    result: list[tuple[str, tuple[str, ...], bytes]] = []
    stream = io.BytesIO(batch.stdout)
    for expected in object_ids:
        header = stream.readline().rstrip(b"\n").split()
        if len(header) != 3 or header[0] != expected:
            raise RuntimeError("git object batch response was malformed")
        size = int(header[2])
        payload = stream.read(size)
        if len(payload) != size or stream.read(1) != b"\n":
            raise RuntimeError("git object batch response was truncated")
        if header[1] == b"blob":
            result.append((expected.decode("ascii"), tuple(sorted(paths_by_object[expected])), payload))
    return result


def _secret_findings(label: str, text: str, fixture_paths: tuple[str, ...] = ()) -> list[str]:
    details: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        allowed = any(line.strip() in SYNTHETIC_SECRET_FIXTURES.get(path, set()) for path in fixture_paths)
        generic = any(_high_confidence_secret(match.group(1)) for match in SECRET_CONTEXT.finditer(line))
        embedded_credential = any(
            _high_confidence_secret(match.group(1), minimum_entropy=3.0)
            for match in URI_CREDENTIAL.finditer(line)
        )
        if not allowed and (
            any(pattern.search(line) for pattern in SECRET_PATTERNS)
            or generic
            or embedded_credential
        ):
            details.append(f"{label}:{number}: secret-like material")
    return details


def _high_confidence_secret(value: str, *, minimum_entropy: float = 3.5) -> bool:
    """Reject credential-shaped random material while sparing obvious examples."""
    candidate = value.rstrip(")]>")
    lowered = candidate.lower()
    if any(marker in lowered for marker in ("example", "placeholder", "redacted", "changeme")):
        return False
    if len(set(candidate)) < 8 or not any(char.isalpha() for char in candidate):
        return False
    frequencies = {char: candidate.count(char) for char in set(candidate)}
    entropy = -sum(
        (count / len(candidate)) * math.log2(count / len(candidate))
        for count in frequencies.values()
    )
    return entropy >= minimum_entropy


def _byte_text_views(payload: bytes) -> tuple[str, ...]:
    """Produce deterministic text views without silently skipping binary blobs."""
    views = [payload.decode("utf-8", errors="replace")]
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        views.append(payload.decode("utf-16", errors="replace"))
    # Credential-bearing binary formats commonly retain printable ASCII strings.
    printable = re.findall(rb"[\x20-\x7e]{8,}", payload)
    if printable:
        views.append("\n".join(item.decode("ascii") for item in printable))
    return tuple(dict.fromkeys(views))


def _secret_findings_bytes(
    label: str, payload: bytes, fixture_paths: tuple[str, ...] = ()
) -> list[str]:
    details: list[str] = []
    for view_index, text in enumerate(_byte_text_views(payload), start=1):
        view_label = label if view_index == 1 else f"{label}:byte-view-{view_index}"
        details.extend(_secret_findings(view_label, text, fixture_paths))
    return details


def _check_secrets(repo: Path, files: list[Path]) -> Check:
    details: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        relative = path.relative_to(repo).as_posix()
        details.extend(_secret_findings_bytes(relative, path.read_bytes(), (relative,)))
    for object_id, paths, payload in _reachable_blob_bytes(repo):
        details.extend(_secret_findings_bytes(f"git-blob:{object_id}", payload, paths))
    details = sorted(set(details))
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
