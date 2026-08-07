from __future__ import annotations

from pathlib import Path
from typing import Any

import tomli
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_BOOTSTRAP = {
    "pip": "26.1.2",
    "setuptools": "83.0.0",
    "wheel": "0.47.0",
}
EXPECTED_RECIPIENT_ENTRY = (
    "-r requirements/recipient-lock.txt",
    "-e .",
)
ALIGN_WITH_CI = frozenset(
    {
        "fastapi",
        "httpx",
        "langgraph",
        "pydantic",
        "pytest",
        "python-dotenv",
        "pyyaml",
        "uvicorn",
    }
)


def _active_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def parse_exact_lock(path: Path, errors: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in _active_lines(path):
        try:
            requirement = Requirement(line)
        except Exception as exc:
            errors.append(f"{path.name}: invalid requirement {line!r}: {exc}")
            continue
        if requirement.url is not None:
            errors.append(f"{path.name}: URL/VCS dependency is not permitted: {line}")
            continue
        specs = list(requirement.specifier)
        if (
            len(specs) != 1
            or specs[0].operator != "=="
            or "*" in specs[0].version
            or requirement.marker is not None
        ):
            errors.append(f"{path.name}: dependency must be an unconditional exact pin: {line}")
            continue
        name = canonicalize_name(requirement.name)
        if name in versions:
            errors.append(f"{path.name}: duplicate dependency name: {name}")
            continue
        versions[name] = specs[0].version
    return versions


def _project_requirement_map(values: list[str], errors: list[str]) -> dict[str, Requirement]:
    result: dict[str, Requirement] = {}
    for value in values:
        try:
            requirement = Requirement(value)
        except Exception as exc:
            errors.append(f"pyproject dependency is invalid: {value!r}: {exc}")
            continue
        name = canonicalize_name(requirement.name)
        if name in result:
            errors.append(f"pyproject duplicate dependency name: {name}")
        result[name] = requirement
    return result


def validate_dependency_contract(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    ci_path = root / "requirements" / "ci-lock.txt"
    bootstrap_path = root / "requirements" / "bootstrap-lock.txt"
    recipient_lock_path = root / "requirements" / "recipient-lock.txt"
    recipient_entry_path = root / "requirements-recipient.txt"
    pyproject_path = root / "pyproject.toml"
    launcher_path = root / "run_factory.sh"
    dockerfile_path = root / "Dockerfile"

    for path in (
        ci_path,
        bootstrap_path,
        recipient_lock_path,
        recipient_entry_path,
        pyproject_path,
        launcher_path,
        dockerfile_path,
    ):
        if not path.is_file():
            errors.append(f"required dependency-contract file missing: {path.relative_to(root)}")

    if errors:
        return {"passed": False, "errors": errors, "warnings": warnings}

    ci = parse_exact_lock(ci_path, errors)
    bootstrap = parse_exact_lock(bootstrap_path, errors)
    recipient = parse_exact_lock(recipient_lock_path, errors)

    if bootstrap != EXPECTED_BOOTSTRAP:
        errors.append(
            "bootstrap-lock.txt must exactly pin "
            + ", ".join(f"{name}=={version}" for name, version in EXPECTED_BOOTSTRAP.items())
        )

    entry_lines = tuple(_active_lines(recipient_entry_path))
    if entry_lines != EXPECTED_RECIPIENT_ENTRY:
        errors.append(
            "requirements-recipient.txt must contain only the governed recipient lock include "
            "followed by the editable first-party install"
        )

    overlap = set(bootstrap).intersection(recipient)
    if overlap:
        errors.append(f"bootstrap and recipient locks overlap: {sorted(overlap)}")

    for name in sorted(ALIGN_WITH_CI):
        ci_version = ci.get(name)
        recipient_version = recipient.get(name)
        if ci_version is None:
            errors.append(f"CI lock missing aligned package: {name}")
        if recipient_version is None:
            errors.append(f"recipient lock missing aligned package: {name}")
        if ci_version is not None and recipient_version is not None and ci_version != recipient_version:
            errors.append(
                f"CI/recipient lock version mismatch for {name}: "
                f"ci={ci_version}, recipient={recipient_version}"
            )

    for name in ("pip", "setuptools"):
        if ci.get(name) != bootstrap.get(name):
            errors.append(
                f"CI/bootstrap lock version mismatch for {name}: "
                f"ci={ci.get(name)}, bootstrap={bootstrap.get(name)}"
            )

    pyproject = tomli.loads(pyproject_path.read_text(encoding="utf-8"))
    build_requirements = pyproject.get("build-system", {}).get("requires", [])
    build_map = _project_requirement_map(list(build_requirements), errors)
    for name in ("setuptools", "wheel"):
        requirement = build_map.get(name)
        expected = bootstrap.get(name)
        if requirement is None or expected is None:
            errors.append(f"build-system missing governed bootstrap dependency: {name}")
            continue
        specs = list(requirement.specifier)
        if len(specs) != 1 or specs[0].operator != "==" or specs[0].version != expected:
            errors.append(f"build-system must exact-pin {name}=={expected}; got {requirement}")

    project_dependencies = _project_requirement_map(
        list(pyproject.get("project", {}).get("dependencies", [])),
        errors,
    )
    for name, requirement in sorted(project_dependencies.items()):
        locked = recipient.get(name)
        if locked is None:
            errors.append(f"recipient lock missing project runtime dependency: {name}")
            continue
        if requirement.specifier and Version(locked) not in requirement.specifier:
            errors.append(
                f"recipient lock version {name}=={locked} violates pyproject constraint "
                f"{requirement.specifier}"
            )

    optional = pyproject.get("project", {}).get("optional-dependencies", {})
    dev = _project_requirement_map(list(optional.get("dev", [])), errors)
    requirement = dev.get("pytest")
    locked = recipient.get("pytest")
    if requirement is None or locked is None:
        errors.append("dev/recipient dependency missing for pytest")
    elif requirement.specifier and Version(locked) not in requirement.specifier:
        errors.append(
            f"recipient lock version pytest=={locked} violates dev constraint "
            f"{requirement.specifier}"
        )

    launcher = launcher_path.read_text(encoding="utf-8")
    for marker in (
        'BOOTSTRAP_REQ_FILE="${ROOT}/requirements/bootstrap-lock.txt"',
        'RECIPIENT_LOCK_FILE="${ROOT}/requirements/recipient-lock.txt"',
        'PYPROJECT_FILE="${ROOT}/pyproject.toml"',
        '"${BOOTSTRAP_REQ_FILE}" "${REQ_FILE}" "${RECIPIENT_LOCK_FILE}" "${PYPROJECT_FILE}"',
        '-r "${BOOTSTRAP_REQ_FILE}"',
        '-r "${REQ_FILE}"',
        'unlocked installed distributions',
        'Recipient dependency lock verification failed after install',
    ):
        if marker not in launcher:
            errors.append(f"run_factory.sh dependency-stamp/install marker missing: {marker}")

    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    for marker in (
        "requirements/bootstrap-lock.txt requirements/recipient-lock.txt ./requirements/",
        "python -m pip install --no-cache-dir -r requirements/bootstrap-lock.txt",
        "python -m pip install --no-cache-dir -r requirements-recipient.txt",
    ):
        if marker not in dockerfile:
            errors.append(f"Dockerfile dependency-lock marker missing: {marker}")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "ci_exact_pin_count": len(ci),
        "bootstrap_exact_pin_count": len(bootstrap),
        "recipient_exact_pin_count": len(recipient),
        "aligned_packages": sorted(ALIGN_WITH_CI),
        "setuptools_version": bootstrap.get("setuptools"),
    }
