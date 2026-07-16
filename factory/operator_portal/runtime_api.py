from __future__ import annotations

from pathlib import Path
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from factory.operator_portal.runtime_contracts import (
    ApprovalGrant,
    RuntimeContractError,
    RuntimeState,
    approval_secret,
    scoped_approval_digest,
    utc_now,
)
from factory.operator_portal.runtime_evidence import RuntimeEvidenceService
from factory.operator_portal.runtime_openapi import RuntimeOpenAPIService
from factory.operator_portal.runtime_scenarios import ScenarioRunner, scenario_catalog
from factory.operator_portal.runtime_store import RuntimeStore
from factory.operator_portal.runtime_supervisor import RuntimeSupervisor
from factory.operator_portal.runtime_views import render_runtime_view


class RuntimeApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(start|restart|stop)$")
    actor: str = Field(default="operator", min_length=1, max_length=80)
    approval_token: str = Field(min_length=1, max_length=512)
    nonce: str | None = Field(default=None, min_length=8, max_length=80)


class RuntimeActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_nonce: str = Field(min_length=8, max_length=80)
    port: int = Field(default=18042, ge=1024, le=65535)


class RuntimeReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: int = Field(default=18042, ge=1024, le=65535)


class RuntimeAPI:
    def __init__(self, *, project_root: Path, state_root: Path | None = None) -> None:
        self.project_root = project_root.resolve()
        self.store = RuntimeStore(project_root=self.project_root, state_root=state_root)
        self.supervisor = RuntimeSupervisor(project_root=self.project_root, store=self.store)
        self.openapi = RuntimeOpenAPIService()
        self.scenarios = ScenarioRunner(store=self.store)
        self.evidence = RuntimeEvidenceService(project_root=self.project_root, store=self.store)

    def approve(self, run_id: str, request: RuntimeApprovalRequest) -> dict[str, Any]:
        try:
            if request.approval_token != approval_secret():
                self.store.append_event(run_id, "runtime_approval_rejected", {"action": request.action, "actor": request.actor})
                raise RuntimeContractError("approval token rejected")
            nonce = request.nonce or f"nonce_{secrets.token_urlsafe(18)}"
            grant = ApprovalGrant(
                run_id=run_id,
                action=request.action,
                nonce=nonce,
                approved_at_utc=utc_now(),
                token_sha256=scoped_approval_digest(
                    run_id=run_id,
                    action=request.action,
                    nonce=nonce,
                    token=approval_secret(),
                ),
            )
            self.store.create_approval(grant)
            return {
                "status": "approved",
                "run_id": run_id,
                "action": request.action,
                "nonce": nonce,
                "approved_at_utc": grant.approved_at_utc,
                "token_persisted": False,
            }
        except RuntimeContractError as exc:
            raise HTTPException(status_code=403, detail={"status": "rejected", "error": str(exc)}) from exc

    def _consume(self, run_id: str, action: str, nonce: str) -> None:
        try:
            self.store.consume_approval(run_id=run_id, action=action, nonce=nonce)
        except RuntimeContractError as exc:
            raise HTTPException(status_code=403, detail={"status": "rejected", "error": str(exc)}) from exc

    def status(self, run_id: str, *, port: int = 18042) -> dict[str, Any]:
        try:
            return self.supervisor.status(run_id=run_id, port=port).as_dict()
        except RuntimeContractError as exc:
            raise HTTPException(status_code=400, detail={"status": "rejected", "error": str(exc)}) from exc

    def start(self, run_id: str, request: RuntimeActionRequest) -> dict[str, Any]:
        self._consume(run_id, "start", request.approval_nonce)
        try:
            return self.supervisor.start(run_id=run_id, port=request.port).as_dict()
        except RuntimeContractError as exc:
            raise HTTPException(status_code=409, detail={"status": "rejected", "error": str(exc)}) from exc

    def restart(self, run_id: str, request: RuntimeActionRequest) -> dict[str, Any]:
        self._consume(run_id, "restart", request.approval_nonce)
        try:
            return self.supervisor.restart(run_id=run_id, port=request.port).as_dict()
        except RuntimeContractError as exc:
            raise HTTPException(status_code=409, detail={"status": "rejected", "error": str(exc)}) from exc

    def stop(self, run_id: str, request: RuntimeActionRequest) -> dict[str, Any]:
        self._consume(run_id, "stop", request.approval_nonce)
        try:
            return self.supervisor.stop(run_id=run_id, port=request.port).as_dict()
        except RuntimeContractError as exc:
            raise HTTPException(status_code=409, detail={"status": "rejected", "error": str(exc)}) from exc

    def events(self, run_id: str) -> dict[str, Any]:
        return {"status": "available", "run_id": run_id, "events": self.store.read_events(run_id)}

    def logs(self, run_id: str) -> dict[str, Any]:
        path = self.store.log_path(run_id)
        if not path.is_file():
            return {"status": "missing", "run_id": run_id, "logs": ""}
        data = path.read_bytes()[-64 * 1024 :]
        return {"status": "available", "run_id": run_id, "logs": data.decode("utf-8", errors="replace").replace("\r", "\\r")}

    def metrics(self, run_id: str, *, port: int = 18042) -> dict[str, Any]:
        status = self.supervisor.status(run_id=run_id, port=port)
        return {
            "status": "available",
            "run_id": run_id,
            "state": status.state.value,
            "event_count": len(self.store.read_events(run_id)),
            "mock_safe_local": True,
            "real_payment_calls": "disabled",
            "default_runtime_llm_calls": 0,
        }

    def openapi_document(self, run_id: str, *, port: int = 18042) -> dict[str, Any]:
        status = self.supervisor.status(run_id=run_id, port=port)
        if status.state not in {RuntimeState.READY, RuntimeState.DEGRADED}:
            raise HTTPException(status_code=409, detail={"status": "rejected", "error": "runtime is not ready"})
        return self.openapi.fetch(
            base_url=f"http://{status.binding.host}:{status.binding.port}",
            owned_port=status.binding.port,
            manifest_sha256=status.binding.manifest_sha256,
        )

    def catalog(self) -> dict[str, Any]:
        return scenario_catalog()

    def run_scenarios(self, run_id: str, *, port: int = 18042) -> dict[str, Any]:
        status = self.supervisor.status(run_id=run_id, port=port)
        if status.state not in {RuntimeState.READY, RuntimeState.DEGRADED}:
            raise HTTPException(status_code=409, detail={"status": "rejected", "error": "runtime is not ready"})
        return self.scenarios.run_all(
            run_id=run_id,
            base_url=f"http://{status.binding.host}:{status.binding.port}",
            owned_port=status.binding.port,
        )

    def evidence_manifest(self, run_id: str) -> dict[str, Any]:
        return self.evidence.build_manifest(run_id=run_id)

    def view(self, run_id: str, *, port: int = 18042) -> str:
        return render_runtime_view(status=self.status(run_id, port=port), events=self.store.read_events(run_id))


def build_runtime_router(*, project_root: Path, state_root: Path | None = None) -> APIRouter:
    api = RuntimeAPI(project_root=project_root, state_root=state_root)
    router = APIRouter(prefix="/operator-portal/api/runtime", tags=["phase50-runtime"])

    @router.get("/runs/{run_id}/status")
    async def runtime_status(run_id: str, port: int = 18042) -> dict[str, Any]:
        return api.status(run_id, port=port)

    @router.post("/runs/{run_id}/approvals")
    async def runtime_approval(run_id: str, request: RuntimeApprovalRequest) -> dict[str, Any]:
        return api.approve(run_id, request)

    @router.post("/runs/{run_id}/start", status_code=202)
    async def runtime_start(run_id: str, request: RuntimeActionRequest) -> dict[str, Any]:
        return api.start(run_id, request)

    @router.post("/runs/{run_id}/restart", status_code=202)
    async def runtime_restart(run_id: str, request: RuntimeActionRequest) -> dict[str, Any]:
        return api.restart(run_id, request)

    @router.post("/runs/{run_id}/stop", status_code=202)
    async def runtime_stop(run_id: str, request: RuntimeActionRequest) -> dict[str, Any]:
        return api.stop(run_id, request)

    @router.get("/runs/{run_id}/events")
    async def runtime_events(run_id: str) -> dict[str, Any]:
        return api.events(run_id)

    @router.get("/runs/{run_id}/logs")
    async def runtime_logs(run_id: str) -> dict[str, Any]:
        return api.logs(run_id)

    @router.get("/runs/{run_id}/metrics")
    async def runtime_metrics(run_id: str, port: int = 18042) -> dict[str, Any]:
        return api.metrics(run_id, port=port)

    @router.get("/runs/{run_id}/openapi")
    async def runtime_openapi(run_id: str, port: int = 18042) -> dict[str, Any]:
        return api.openapi_document(run_id, port=port)

    @router.get("/scenario-catalog")
    async def runtime_scenario_catalog() -> dict[str, Any]:
        return api.catalog()

    @router.post("/runs/{run_id}/scenarios")
    async def runtime_run_scenarios(run_id: str, request: RuntimeReadRequest) -> dict[str, Any]:
        return api.run_scenarios(run_id, port=request.port)

    @router.get("/runs/{run_id}/evidence")
    async def runtime_evidence(run_id: str) -> dict[str, Any]:
        return api.evidence_manifest(run_id)

    @router.get("/runs/{run_id}/view", include_in_schema=False)
    async def runtime_view(run_id: str, port: int = 18042) -> Response:
        return Response(content=api.view(run_id, port=port), media_type="text/html")

    @router.get("/runs/{run_id}/downloads/evidence")
    async def runtime_evidence_download(run_id: str) -> Response:
        archive = api.evidence.archive(run_id=run_id)
        return Response(
            content=archive.read_bytes(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{run_id}_runtime_evidence.zip"'},
        )

    return router
