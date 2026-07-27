"""Pytest import path bootstrap for the local src-layout package."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, cast

import httpx
import pytest

import fastapi.testclient
import fastapi.routing

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


async def _run_in_test_threadpool(func: Any, *args: Any, **kwargs: Any) -> Any:
    return func(*args, **kwargs)


cast(Any, fastapi.routing).run_in_threadpool = _run_in_test_threadpool


class ASGISyncClient:
    __test__ = False

    def __init__(self, app: Any, *, base_url: str = "http://testserver", **_: Any) -> None:
        self.app = app
        self.base_url = base_url

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async def _request() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url=self.base_url) as client:
                return await client.request(method, url, **kwargs)

        import asyncio

        return asyncio.run(_request())

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def __enter__(self) -> "ASGISyncClient":
        return self

    def __exit__(self, *_: Any) -> None:
        return None


cast(Any, fastapi.testclient).TestClient = ASGISyncClient


@pytest.fixture(autouse=True)
def _explicit_test_approval_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "UPI_APP_FACTORY_RUNTIME_APPROVAL_TOKEN",
        "phase50-test-runtime-approval-fixture",
    )
    monkeypatch.setenv(
        "UPI_APP_FACTORY_PORTFOLIO_APPROVAL_TOKEN",
        "phase51-test-portfolio-approval-fixture",
    )
