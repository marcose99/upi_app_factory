#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_yaml(path: str) -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(path))
    if not isinstance(payload, dict):
        raise AssertionError(f"{path} must contain a YAML mapping.")
    return payload


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate() -> dict[str, Any]:
    errors: list[str] = []
    compose = _load_yaml("compose.yaml")
    platforms = _load_yaml("config/supported_platforms.yaml")
    dockerfile = _read_text("Dockerfile")
    dockerignore = _read_text(".dockerignore")
    pyproject = _read_text("pyproject.toml")
    readme = _read_text("README.md")
    env_spec = _read_text("docs/handover/ENVIRONMENT_SPEC.md")
    script = _read_text("scripts/run_docker_factory_portal.py")

    service = compose.get("services", {}).get("factory-portal", {})
    environment = service.get("environment", {})
    ports = service.get("ports", [])
    volumes = service.get("volumes", [])
    healthcheck = service.get("healthcheck", {})

    _require(service.get("build", {}).get("dockerfile") == "Dockerfile", "compose must build the root Dockerfile", errors)
    _require(service.get("read_only") is True, "compose service must use a read-only root filesystem", errors)
    _require(service.get("restart") == "no", "compose service must not auto-restart", errors)
    expected_port_mapping = "127.0.0.1:${UPI_APP_FACTORY_HOST_PORT:-${UPI_APP_FACTORY_PORT:-8036}}:8036"
    _require(expected_port_mapping in ports, "host port must be configurable from UPI_APP_FACTORY_HOST_PORT or UPI_APP_FACTORY_PORT and loopback-published", errors)
    _require("factory-portal-var:/app/.var" in volumes, "compose must persist /app/.var in a named volume", errors)
    _require(bool(healthcheck.get("test")), "compose healthcheck must be present", errors)
    _require(healthcheck.get("interval") == "5s", "compose healthcheck interval must support bounded startup gates", errors)
    _require(healthcheck.get("timeout") == "3s", "compose healthcheck timeout must be short and deterministic", errors)
    _require(healthcheck.get("start_period") == "5s", "compose healthcheck start period must support bounded startup gates", errors)
    _require(healthcheck.get("retries") == 12, "compose healthcheck retries must preserve a one-minute readiness budget", errors)
    _require("timeout=2" in " ".join(str(part) for part in healthcheck.get("test", [])), "compose health probe must finish inside the Docker timeout", errors)
    _require(environment.get("FACTORY_LLM_ENABLED") == "0", "compose must disable FACTORY_LLM_ENABLED", errors)
    _require(environment.get("UPI_APP_FACTORY_LLM_ENABLED") == "0", "compose must disable UPI_APP_FACTORY_LLM_ENABLED", errors)
    _require(environment.get("REAL_PAYMENT_CALLS") == "disabled", "compose must disable real payment calls", errors)
    _require(environment.get("UPI_APP_FACTORY_REAL_PAYMENT_CALLS") == "disabled", "compose must disable namespaced real payment calls", errors)
    _require(environment.get("MOCK_BOUNDARY") == "1", "compose must declare mock boundary", errors)
    _require(
        environment.get("UPI_APP_FACTORY_PORTAL_PUBLICATION_ROOT") == "/app/.var/operator_portal/publications",
        "compose must route generated portal publications to the writable /app/.var volume",
        errors,
    )

    for marker in [
        "USER appfactory",
        "VOLUME [\"/app/.var\"]",
        "HEALTHCHECK",
        "--interval=5s",
        "--start-period=5s",
        "--retries=12",
        "scripts/run_docker_factory_portal.py",
        "COPY --chown=appfactory:appfactory src ./src",
        "COPY --chown=appfactory:appfactory tools ./tools",
        "PIP_NO_CACHE_DIR=1",
        "requirements/bootstrap-lock.txt requirements/recipient-lock.txt ./requirements/",
        "python -m pip install --no-cache-dir -r requirements/bootstrap-lock.txt",
        "python -m pip install --no-cache-dir -r requirements-recipient.txt",
    ]:
        _require(marker in dockerfile, f"Dockerfile missing {marker}", errors)
    bootstrap_install = "python -m pip install --no-cache-dir -r requirements/bootstrap-lock.txt"
    recipient_install = "python -m pip install --no-cache-dir -r requirements-recipient.txt"
    if (
        "COPY --chown=appfactory:appfactory src ./src" in dockerfile
        and bootstrap_install in dockerfile
        and recipient_install in dockerfile
    ):
        _require(
            dockerfile.index("COPY --chown=appfactory:appfactory src ./src")
            < dockerfile.index(bootstrap_install)
            < dockerfile.index(recipient_install),
            "Dockerfile must copy package sources before bootstrap-lock and recipient-lock installation",
            errors,
        )
    _require("COPY --chown=appfactory:appfactory . ." not in dockerfile, "Dockerfile must not bulk-copy the full repository", errors)
    _require(".git" in dockerignore and ".var" in dockerignore, ".dockerignore must exclude git metadata and local state", errors)
    _require(
        '"httpx>=0.27"' in pyproject,
        "project metadata must retain Starlette/FastAPI-compatible httpx",
        errors,
    )
    _require(
        '"httpx2"' not in pyproject,
        "project metadata must not install unsupported httpx2 in the Docker portal image",
        errors,
    )

    native = platforms.get("runtime_claims", {}).get("native", {})
    docker_route = platforms.get("runtime_claims", {}).get("docker_compose", {})
    _require("native Windows" in native.get("not_claimed", []), "contract must not claim native Windows support", errors)
    _require("native macOS" in native.get("not_claimed", []), "contract must not claim native macOS support", errors)
    _require(docker_route.get("host_publication") == "loopback_only", "Docker route must be loopback-only on the host", errors)
    _require(platforms.get("certification_posture") == "certification_ready_not_certified", "certification posture must remain non-certified", errors)
    _require(platforms.get("non_claims", {}).get("production_ready") is False, "contract must not claim production readiness", errors)

    normalized_docs = " ".join((readme + env_spec).split())
    for marker in [
        "docker compose up --build",
        "docker compose down",
        "UPI_APP_FACTORY_HOST_PORT",
        "Linux Docker Engine",
        "macOS Docker Desktop",
        "Windows Docker Desktop",
    ]:
        _require(marker in readme + env_spec, f"documentation missing {marker}", errors)
    _require(
        "Do not use this route as evidence of native Windows or native macOS support" in normalized_docs,
        "documentation missing native Windows/macOS non-claim",
        errors,
    )

    for marker in [
        "_require_mock_only_environment",
        "create_web_ui_app",
        "publication_root",
        "portfolio_state_root",
        "runtime_state_root",
    ]:
        _require(marker in script, f"Docker runner missing {marker}", errors)

    if errors:
        raise AssertionError("\n".join(errors))
    return {
        "status": "passed",
        "contract": platforms["contract_id"],
        "compose_service": "factory-portal",
        "host_publication": expected_port_mapping,
        "certification_posture": platforms["certification_posture"],
    }


def main() -> int:
    print(json.dumps(validate(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
