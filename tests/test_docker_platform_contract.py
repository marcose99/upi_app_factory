from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_supported_platform_contract_scopes_routes_without_native_windows_macos_claims() -> None:
    contract = yaml.safe_load((PROJECT_ROOT / "config/supported_platforms.yaml").read_text(encoding="utf-8"))

    native = contract["runtime_claims"]["native"]
    docker_compose = contract["runtime_claims"]["docker_compose"]

    assert native["supported"] == [{"platform": "Ubuntu/Linux", "route": "bash and Python local operator portal"}]
    assert "native Windows" in native["not_claimed"]
    assert "native macOS" in native["not_claimed"]
    assert {entry["platform"] for entry in docker_compose["supported"]} == {
        "Linux Docker Engine with Compose",
        "macOS Docker Desktop",
        "Windows Docker Desktop",
    }
    assert docker_compose["host_publication"] == "loopback_only"
    assert contract["certification_posture"] == "certification_ready_not_certified"
    assert contract["non_claims"]["production_ready"] is False
    assert contract["mock_boundary"]["llm_default_enabled"] is False
    assert contract["mock_boundary"]["real_payment_calls"] == "disabled"


def test_compose_and_dockerfile_local_mock_only_contract() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    service = compose["services"]["factory-portal"]
    env = service["environment"]

    assert service["build"] == {"context": ".", "dockerfile": "Dockerfile"}
    assert service["ports"] == ["127.0.0.1:${UPI_APP_FACTORY_HOST_PORT:-${UPI_APP_FACTORY_PORT:-8036}}:8036"]
    assert service["volumes"] == ["factory-portal-var:/app/.var"]
    assert service["read_only"] is True
    assert service["restart"] == "no"
    assert service["user"] == "${UPI_APP_FACTORY_CONTAINER_UID:-1000}:${UPI_APP_FACTORY_CONTAINER_GID:-1000}"
    assert service["healthcheck"]["test"][0] == "CMD-SHELL"
    assert service["healthcheck"]["interval"] == "5s"
    assert service["healthcheck"]["timeout"] == "3s"
    assert service["healthcheck"]["start_period"] == "5s"
    assert service["healthcheck"]["retries"] == 12
    assert "timeout=2" in " ".join(service["healthcheck"]["test"])
    assert env["FACTORY_LLM_ENABLED"] == "0"
    assert env["UPI_APP_FACTORY_LLM_ENABLED"] == "0"
    assert env["REAL_PAYMENT_CALLS"] == "disabled"
    assert env["UPI_APP_FACTORY_REAL_PAYMENT_CALLS"] == "disabled"
    assert env["MOCK_BOUNDARY"] == "1"
    assert env["UPI_APP_FACTORY_PORTAL_PUBLICATION_ROOT"] == "/app/.var/operator_portal/publications"

    assert "USER appfactory" in dockerfile
    assert "VOLUME [\"/app/.var\"]" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--interval=5s" in dockerfile
    assert "--start-period=5s" in dockerfile
    assert "--retries=12" in dockerfile
    assert "scripts/run_docker_factory_portal.py" in dockerfile
    assert "COPY --chown=appfactory:appfactory src ./src" in dockerfile
    bootstrap_install = "python -m pip install --no-cache-dir -r requirements/bootstrap-lock.txt"
    recipient_install = "python -m pip install --no-cache-dir -r requirements-recipient.txt"
    assert "requirements/bootstrap-lock.txt requirements/recipient-lock.txt ./requirements/" in dockerfile
    assert dockerfile.index("COPY --chown=appfactory:appfactory src ./src") < dockerfile.index(
        bootstrap_install
    ) < dockerfile.index(recipient_install)
    assert "COPY --chown=appfactory:appfactory tools ./tools" in dockerfile
    assert "COPY --chown=appfactory:appfactory . ." not in dockerfile
    assert ".git" in dockerignore
    assert ".var" in dockerignore
    assert '"httpx>=0.27"' in pyproject
    assert '"httpx2"' not in pyproject


def test_docker_contract_validation_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_docker_platform_contract.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "supported-platform-contract-v32" in result.stdout
