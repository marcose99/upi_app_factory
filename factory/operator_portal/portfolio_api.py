from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from factory.application_engineering.portfolio import (
    PortfolioCatalogue,
    PortfolioComparator,
    PortfolioError,
    PortfolioEvidenceService,
    PortfolioScenarioRunner,
    PortfolioStore,
    PortfolioSupervisor,
    RuntimeState,
    VersionState,
    approve_action,
)


class PortfolioApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(start|restart|stop|stop_all|quarantine|retire)$")
    scope: str = Field(min_length=1, max_length=160)
    actor: str = Field(default="operator", min_length=1, max_length=80)
    approval_token: str = Field(min_length=1, max_length=512)
    nonce: str | None = Field(default=None, min_length=8, max_length=80)


class PortfolioRuntimeActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    version_id: str
    run_id: str
    port: int = Field(ge=1024, le=65535)
    approval_nonce: str = Field(min_length=8, max_length=80)


class PortfolioReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    version_id: str
    run_id: str
    port: int = Field(ge=1024, le=65535)


class PortfolioVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    version_id: str


class PortfolioCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_app_id: str
    left_version_id: str
    right_app_id: str
    right_version_id: str


class PortfolioLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    version_id: str
    target_state: str = Field(pattern=r"^(quarantined|retired)$")
    approval_nonce: str = Field(min_length=8, max_length=80)


class PortfolioAPI:
    def __init__(self, *, project_root: Path, state_root: Path | None = None) -> None:
        self.store = PortfolioStore(project_root=project_root, state_root=state_root)
        self.catalogue = PortfolioCatalogue(store=self.store)
        self.supervisor = PortfolioSupervisor(store=self.store, catalogue=self.catalogue)
        self.scenarios = PortfolioScenarioRunner(store=self.store)
        self.evidence = PortfolioEvidenceService(store=self.store)
        self.comparator = PortfolioComparator()

    def catalogue_payload(self) -> dict[str, Any]:
        try:
            versions = [item.as_dict() for item in self.catalogue.list_versions()]
            return {
                "status": "available",
                "local_only": True,
                "loopback_only": True,
                "mock_only": True,
                "certification_posture": "certification-ready-not-certified",
                "versions": versions,
                "catalogue": self.catalogue.catalogue(),
            }
        except PortfolioError as exc:
            raise HTTPException(
                status_code=409,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc

    def approve(self, request: PortfolioApprovalRequest) -> dict[str, Any]:
        try:
            return approve_action(
                store=self.store,
                action=request.action,
                scope=request.scope,
                actor=request.actor,
                token=request.approval_token,
                nonce=request.nonce,
            )
        except PortfolioError as exc:
            raise HTTPException(
                status_code=403,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc

    def start(self, request: PortfolioRuntimeActionRequest) -> dict[str, Any]:
        self._consume(action="start", scope=request.run_id, nonce=request.approval_nonce)
        try:
            return self.supervisor.start(
                app_id=request.app_id,
                version_id=request.version_id,
                run_id=request.run_id,
                port=request.port,
            ).as_dict()
        except PortfolioError as exc:
            raise HTTPException(
                status_code=409,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc

    def status(self, request: PortfolioReadRequest) -> dict[str, Any]:
        try:
            return self.supervisor.status(
                app_id=request.app_id,
                version_id=request.version_id,
                run_id=request.run_id,
                port=request.port,
            ).as_dict()
        except PortfolioError as exc:
            raise HTTPException(
                status_code=400,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc

    def openapi_document(
        self,
        request: PortfolioVersionRequest,
    ) -> dict[str, Any]:
        try:
            version = self.catalogue.get(
                app_id=request.app_id,
                version_id=request.version_id,
            )
        except PortfolioError as exc:
            raise HTTPException(
                status_code=404,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc

        openapi = version.manifest.get("openapi")
        if not isinstance(openapi, dict):
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "rejected",
                    "error": "registered version OpenAPI manifest is unavailable",
                },
            )

        paths = openapi.get("paths")
        if not isinstance(paths, dict):
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "rejected",
                    "error": "registered version OpenAPI paths are unavailable",
                },
            )

        endpoint_inventory = sorted(
            path
            for path in paths
            if isinstance(path, str) and path.startswith("/")
        )
        http_methods = {
            "delete",
            "get",
            "head",
            "options",
            "patch",
            "post",
            "put",
            "trace",
        }
        method_inventory: dict[str, list[str]] = {}

        for path in endpoint_inventory:
            path_item = paths[path]
            if isinstance(path_item, dict):
                methods = sorted(
                    method.upper()
                    for method in path_item
                    if (
                        isinstance(method, str)
                        and method.lower() in http_methods
                    )
                )
            else:
                methods = []
            method_inventory[path] = methods

        return {
            "status": "available",
            "local_only": True,
            "loopback_only": True,
            "mock_only": True,
            "certification_posture": (
                "certification-ready-not-certified"
            ),
            "app_id": version.app_id,
            "version_id": version.version_id,
            "version_identity_sha256": version.identity_sha256,
            "endpoint_inventory": endpoint_inventory,
            "method_inventory": method_inventory,
            "openapi": openapi,
        }

    def restart(self, request: PortfolioRuntimeActionRequest) -> dict[str, Any]:
        self._consume(action="restart", scope=request.run_id, nonce=request.approval_nonce)
        try:
            return self.supervisor.restart(
                app_id=request.app_id,
                version_id=request.version_id,
                run_id=request.run_id,
                port=request.port,
            ).as_dict()
        except PortfolioError as exc:
            raise HTTPException(
                status_code=409,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc

    def stop(self, request: PortfolioRuntimeActionRequest) -> dict[str, Any]:
        self._consume(action="stop", scope=request.run_id, nonce=request.approval_nonce)
        try:
            return self.supervisor.stop(
                app_id=request.app_id,
                version_id=request.version_id,
                run_id=request.run_id,
                port=request.port,
            ).as_dict()
        except PortfolioError as exc:
            raise HTTPException(
                status_code=409,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc

    def stop_all(self, *, approval_nonce: str) -> dict[str, Any]:
        self._consume(action="stop_all", scope="portfolio", nonce=approval_nonce)
        return self.supervisor.stop_all()

    def run_scenarios(
        self,
        request: PortfolioReadRequest,
        *,
        parallel: bool = False,
    ) -> dict[str, Any]:
        status = self.supervisor.status(
            app_id=request.app_id,
            version_id=request.version_id,
            run_id=request.run_id,
            port=request.port,
        )
        if status.state not in {RuntimeState.READY, RuntimeState.DEGRADED}:
            raise HTTPException(
                status_code=409,
                detail={"status": "rejected", "error": "runtime is not ready"},
            )
        return self.scenarios.run_for_status(status, parallel=parallel)

    def aggregate_scenarios(self, *, parallel: bool = False) -> dict[str, Any]:
        statuses = [
            status
            for status in self.supervisor.runtime_statuses()
            if status.state in {RuntimeState.READY, RuntimeState.DEGRADED}
        ]
        return self.scenarios.run_portfolio(statuses, parallel=parallel)

    def compare(self, request: PortfolioCompareRequest) -> dict[str, Any]:
        left = self.catalogue.get(app_id=request.left_app_id, version_id=request.left_version_id)
        right = self.catalogue.get(app_id=request.right_app_id, version_id=request.right_version_id)
        return self.comparator.compare(left, right)

    def transition_version(self, request: PortfolioLifecycleRequest) -> dict[str, Any]:
        action = (
            "quarantine"
            if request.target_state == VersionState.QUARANTINED.value
            else "retire"
        )
        scope = f"{request.app_id}:{request.version_id}"
        self._consume(action=action, scope=scope, nonce=request.approval_nonce)
        target = VersionState(request.target_state)
        return self.catalogue.transition_version(
            app_id=request.app_id,
            version_id=request.version_id,
            target=target,
        ).as_dict()

    def evidence_manifest(self) -> dict[str, Any]:
        return self.evidence.manifest()

    def view(self) -> str:
        return render_portfolio_view(
            self.catalogue_payload(),
            [status.as_dict() for status in self.supervisor.runtime_statuses()],
        )

    def _consume(self, *, action: str, scope: str, nonce: str) -> None:
        try:
            self.store.consume_approval(action=action, scope=scope, nonce=nonce)
        except PortfolioError as exc:
            raise HTTPException(
                status_code=403,
                detail={"status": "rejected", "error": str(exc)},
            ) from exc


def render_portfolio_view(catalogue: dict[str, Any], runtimes: list[dict[str, Any]]) -> str:
    version_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item['app_id']))}</td>"
        f"<td>{escape(str(item['version_id']))}</td>"
        f"<td>{escape(str(item['state']))}</td>"
        f"<td>{escape(str(item['generated_run_id']))}</td>"
        f"<td>{escape(str(item['evidence_checksum']))}</td>"
        "</tr>"
        for item in catalogue["versions"]
    )
    runtime_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item['binding']['run_id']))}</td>"
        f"<td>{escape(str(item['binding']['app_id']))}</td>"
        f"<td>{escape(str(item['binding']['version_id']))}</td>"
        f"<td>{escape(str(item['state']))}</td>"
        f"<td>{escape(str(item['binding']['host']))}:{escape(str(item['binding']['port']))}</td>"
        "</tr>"
        for item in runtimes
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Portfolio Operations</title></head>
<body>
<main>
<h1>Governed Portfolio Operations</h1>
<p>Local-only, loopback-only, mock-only. Certification-ready-not-certified.
Production deployment disabled.</p>
<section aria-label="filters">
<input aria-label="Filter applications" placeholder="Filter applications">
</section>
<section><h2>Portfolio Catalogue</h2><table><tbody>{version_rows}</tbody></table></section>
<section><h2>Runtime Controls</h2>
<button data-action="start">Start</button>
<button data-action="restart">Restart</button>
<button data-action="stop">Stop</button>
<button data-action="stop_all">Stop All</button>
</section>
<section><h2>Aggregate Status</h2><table><tbody>{runtime_rows}</tbody></table></section>
<section><h2>Evidence</h2>
<a href="/operator-portal/api/portfolio/evidence">Aggregate evidence</a>
</section>
<section><h2>Comparison</h2><button data-action="compare">Compare Versions</button></section>
</main>
</body>
</html>"""


def build_portfolio_router(*, project_root: Path, state_root: Path | None = None) -> APIRouter:
    api = PortfolioAPI(project_root=project_root, state_root=state_root)
    router = APIRouter(prefix="/operator-portal/api/portfolio", tags=["phase51-portfolio"])

    @router.get("/catalogue")
    async def portfolio_catalogue() -> dict[str, Any]:
        return api.catalogue_payload()

    @router.post("/approvals")
    async def portfolio_approval(request: PortfolioApprovalRequest) -> dict[str, Any]:
        return api.approve(request)

    @router.post("/runtime/start", status_code=202)
    async def portfolio_start(request: PortfolioRuntimeActionRequest) -> dict[str, Any]:
        return api.start(request)

    @router.post("/runtime/status")
    async def portfolio_status(request: PortfolioReadRequest) -> dict[str, Any]:
        return api.status(request)

    @router.post("/runtime/openapi")
    async def portfolio_openapi(
        request: PortfolioVersionRequest,
    ) -> dict[str, Any]:
        return api.openapi_document(request)

    @router.post("/runtime/restart", status_code=202)
    async def portfolio_restart(request: PortfolioRuntimeActionRequest) -> dict[str, Any]:
        return api.restart(request)

    @router.post("/runtime/stop", status_code=202)
    async def portfolio_stop(request: PortfolioRuntimeActionRequest) -> dict[str, Any]:
        return api.stop(request)

    @router.post("/runtime/stop-all", status_code=202)
    async def portfolio_stop_all(approval_nonce: str) -> dict[str, Any]:
        return api.stop_all(approval_nonce=approval_nonce)

    @router.post("/scenarios")
    async def portfolio_scenarios(
        request: PortfolioReadRequest,
        parallel: bool = False,
    ) -> dict[str, Any]:
        return api.run_scenarios(request, parallel=parallel)

    @router.post("/scenarios/aggregate")
    async def portfolio_aggregate_scenarios(parallel: bool = False) -> dict[str, Any]:
        return api.aggregate_scenarios(parallel=parallel)

    @router.post("/compare")
    async def portfolio_compare(request: PortfolioCompareRequest) -> dict[str, Any]:
        return api.compare(request)

    @router.post("/lifecycle")
    async def portfolio_lifecycle(request: PortfolioLifecycleRequest) -> dict[str, Any]:
        return api.transition_version(request)

    @router.get("/evidence")
    async def portfolio_evidence() -> dict[str, Any]:
        return api.evidence_manifest()

    @router.get("/view", include_in_schema=False)
    async def portfolio_view() -> Response:
        return Response(content=api.view(), media_type="text/html")

    return router
