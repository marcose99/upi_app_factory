from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import httpx
from fastapi import FastAPI

from factory.operator_portal.local_web_api import LOCAL_API_SAFETY_BOUNDARIES, create_app
from factory.operator_portal.token_economics_dashboard import build_dashboard
from factory.token_economics import (
    build_token_economics_summary,
    classify_generated_application_token_economics,
)


ROOT = Path(__file__).resolve().parents[1]
ROOT_COMMAND = "factoryctl"


async def _request(app: FastAPI, method: str, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://local-operator-portal") as client:
        return await client.request(method, path)


def request(app: FastAPI, method: str, path: str) -> httpx.Response:
    return asyncio.run(_request(app, method, path))


def run_factoryctl(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src = str(ROOT / "src")
    old = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src if not old else src + os.pathsep + old
    return subprocess.run(
        [str(ROOT / ROOT_COMMAND), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_token_economics_summary_stays_local_mock_only_and_deterministic() -> None:
    summary = build_token_economics_summary(ROOT)

    assert summary["schema_version"] == "token-economics-portal-summary.v1"
    assert summary["rate_cards"]["count"] >= 2
    assert summary["mock_boundaries"] == {
        "live_provider_calls_allowed": False,
        "real_payment_calls": "disabled",
        "runtime_llm_calls_default": 0,
    }
    assert summary["generated_application_applicability"]["status"] == "NOT_APPLICABLE"
    assert summary["generated_application_applicability"]["runtime_llm_calls_default"] == 0


def test_token_economics_dashboard_and_local_api_expose_budget_and_boundaries() -> None:
    dashboard = build_dashboard(ROOT)

    assert dashboard["status"] == "available"
    assert dashboard["default_stage_budget"]["budget_id"] == "governed-local-stage-default"
    assert dashboard["summary"]["rate_cards"]["count"] >= 2

    app = create_app(project_root=ROOT)
    response = request(app, "GET", "/portal/token-economics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert payload["payload"]["status"] == "available"
    assert payload["payload"]["default_stage_budget"]["budget_id"] == "governed-local-stage-default"
    assert payload["safety_boundaries"] == LOCAL_API_SAFETY_BOUNDARIES


def test_factoryctl_token_economics_summary_delegates_to_offline_cli() -> None:
    result = run_factoryctl("token-economics", "summary")

    assert result.returncode == 0, result.stdout
    stdout_lines = [line for line in result.stdout.splitlines() if not line.startswith("+ ")]
    payload = json.loads("\n".join(stdout_lines))
    assert payload["schema_version"] == "token-economics-portal-summary.v1"
    assert payload["mock_boundaries"]["live_provider_calls_allowed"] is False

def test_generated_application_token_economics_applicability_requires_declared_model_activity() -> None:
    not_applicable = classify_generated_application_token_economics(
        requirements_text="runtime_llm_calls_default: 0\nThis flow uses deterministic rules only.",
        runtime_llm_calls_default=0,
    )
    applicable = classify_generated_application_token_economics(
        requirements_text="Runtime orchestration includes agent review and model scoring.",
        runtime_llm_calls_default=0,
    )

    assert not_applicable == {
        "status": "NOT_APPLICABLE",
        "reason": "no LLM, agent, or model activity is declared in the generated application contract",
        "runtime_llm_calls_default": 0,
    }
    assert applicable["status"] == "APPLICABLE"
    assert applicable["runtime_llm_calls_default"] == 0
