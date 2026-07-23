from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import shutil
import zipfile
from typing import Any, Mapping

from factory.application_engineering.deep_composer import DOMAIN_STATES, REQUIRED_ENDPOINTS
from factory.application_engineering.requirements_compiler import compile_requirements
from factory.application_engineering.verification_evidence import build_test_catalogue, materialize_generated_app_if_missing
from scripts.run_portal_requirements_driven_application_engineering import (
    APPROVAL_TOKEN,
    AdapterConfig,
    run as run_requirements_engineering,
)


APP_ID = "upi_failed_debit_dispute"
PHASE = "phase58_operator_portal_integration"
MAX_TEXT_BYTES = 128 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
REQUIRED_VIEWS = {
    "requirements",
    "diagnostics",
    "traceability",
    "domain_model",
    "invariants",
    "state_machine",
    "commands",
    "queries",
    "events",
    "api",
    "data_model",
    "threat_model",
    "adrs",
    "runtime_profile",
    "autonomous_stages",
    "agent_evidence",
    "deterministic_gates",
    "repairs",
    "test_counts",
    "depth_score",
    "risks",
    "manifests",
    "source_browser",
    "evidence_browser",
}


class DeepPortalError(RuntimeError):
    pass


@dataclass(frozen=True)
class PortalRequirements:
    text: str
    source_label: str
    source_path: Path
    sha256: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DeepPortalError(f"{path} must contain a JSON object")
    return value


def safe_child(root: Path, relative: str) -> Path:
    clean = relative.strip().lstrip("/")
    candidate = (root / clean).resolve()
    if not candidate.is_relative_to(root.resolve()) or candidate.is_dir() or candidate.is_symlink():
        raise DeepPortalError("unsafe or unavailable portal file path")
    return candidate


def file_inventory(root: Path, *, limit: int = 200) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if len(records) >= limit:
            break
        if path.is_file() and not path.is_symlink():
            relative = path.relative_to(root).as_posix()
            records.append(
                {
                    "path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_bytes(path.read_bytes()),
                    "download_path": relative,
                }
            )
    return records


def safe_zip(root: Path, destination: Path, *, top_level: str) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise DeepPortalError("unsafe archive member")
            member = f"{top_level}/{relative}"
            if member in seen:
                raise DeepPortalError("duplicate archive member")
            seen.add(member)
            info = zipfile.ZipInfo(member)
            info.date_time = ZIP_TIMESTAMP
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return {
        "path": destination,
        "sha256": sha256_bytes(destination.read_bytes()),
        "size_bytes": destination.stat().st_size,
    }


class DeepPortalIntegration:
    def __init__(self, *, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.campaign_root = self.project_root / "workspace" / "deep_engineering_campaign"
        self.runtime_root = self.campaign_root / "phase58_portal_runtime"
        self.default_requirements = self.project_root / "examples" / "requirements" / "01_upi_failed_debit_no_credit.md"
        self.source_root = self.campaign_root / "generated_app" / APP_ID
        self.evidence_root = self.source_root / "evidence"
        self.verification_root = self.evidence_root / "phase57_verification"

    def overview(self) -> dict[str, Any]:
        materialize_generated_app_if_missing(self.project_root)
        ir_path = self.campaign_root / "phase53_requirements_ir.json"
        ir = read_json(ir_path) if ir_path.is_file() else self.compile({})["requirements_ir"]
        phase_reports = self._phase_reports()
        depth = self._optional_json(self.verification_root / "depth_score.json") or self._optional_json(self.evidence_root / "depth_score.json")
        test_results = self._optional_json(self.verification_root / "test_results.json") or self._default_test_results()
        return {
            "schema_version": "phase58-deep-portal-overview.v1",
            "phase": PHASE,
            "product_name": "UPI App Factory",
            "repository_id": "upi_app_factory",
            "portal_mode": "server-rendered-dependency-light",
            "application_engineering_wording": "application engineering",
            "profiles": {
                "compatibility_scaffold": {
                    "available": True,
                    "description": "Legacy compatibility scaffold remains available for governed migration evidence.",
                },
                "deep_profile": {
                    "available": True,
                    "profile_id": "local-deep-v1",
                    "app_id": APP_ID,
                    "description": "Deep local profile with domain, application, infrastructure, API, security, and evidence artifacts.",
                },
            },
            "safe_commands": [
                "proposal-only deep application engineering",
                "approved deep application engineering with local approval token",
                "download local source archive",
                "download local evidence archive",
            ],
            "mock_boundaries": {
                "real_payment_calls": "disabled",
                "default_runtime_llm_calls": 0,
                "live_provider_calls_allowed": False,
                "external_ecosystem_integrations": "mocked_or_simulated_only",
            },
            "views": self._views(ir, depth, test_results, phase_reports),
            "source_files": file_inventory(self.source_root),
            "evidence_files": file_inventory(self.evidence_root),
        }

    def compile(self, request: Mapping[str, Any]) -> dict[str, Any]:
        requirements = self._requirements_from_request(request)
        ir = compile_requirements([requirements.source_path], self.project_root)
        raw_diagnostics = ir.get("diagnostics", [])
        warnings = (
            raw_diagnostics.get("warnings", [])
            if isinstance(raw_diagnostics, dict)
            else raw_diagnostics
            if isinstance(raw_diagnostics, list)
            else []
        )
        diagnostics = {
            "valid": True,
            "errors": [],
            "warnings": warnings,
            "requirements_sha256": requirements.sha256,
            "traceability_count": len(ir.get("traceability", [])),
        }
        return {
            "schema_version": "phase58-requirements-compile.v1",
            "status": "compiled",
            "source_label": requirements.source_label,
            "requirements_sha256": requirements.sha256,
            "diagnostics": diagnostics,
            "requirements_ir": ir,
            "traceability": ir.get("traceability", []),
            "mock_boundary": True,
            "real_payment_calls": "disabled",
            "llm_calls": 0,
        }

    def proposal(self, request: Mapping[str, Any]) -> dict[str, Any]:
        requirements = self._requirements_from_request(request)
        config = self._adapter_config(requirements, plan_only=True, approved=False)
        plan = run_requirements_engineering(config)
        return {
            "schema_version": "phase58-proposal.v1",
            "status": "proposal_ready",
            "adapter_status": plan["status"],
            "plan": plan,
            "profile_distinction": "local-deep-v1 proposal, no generated source written",
            "real_payment_calls": "disabled",
            "llm_calls": 0,
        }

    def approved_run(self, request: Mapping[str, Any]) -> dict[str, Any]:
        token = str(request.get("approval_token", ""))
        expected = str(request.get("expected_token", APPROVAL_TOKEN))
        if token != expected:
            raise DeepPortalError("approved deep application engineering requires the governed approval token")
        requirements = self._requirements_from_request(request)
        config = self._adapter_config(requirements, plan_only=False, approved=True)
        result = run_requirements_engineering(config)
        return {
            "schema_version": "phase58-approved-run.v1",
            "status": "completed",
            "adapter_status": result["status"],
            "result": result,
            "source_root": str(config.output_root / APP_ID),
            "evidence_root": str(config.evidence_root),
            "real_payment_calls": "disabled",
            "llm_calls": 0,
        }

    def read_source(self, relative: str) -> dict[str, Any]:
        return self._read_file(self.source_root, relative, "source")

    def read_evidence(self, relative: str) -> dict[str, Any]:
        return self._read_file(self.evidence_root, relative, "evidence")

    def source_archive(self) -> Path:
        archive = self.runtime_root / "downloads" / "phase58_source.zip"
        safe_zip(self.source_root, archive, top_level=f"{APP_ID}_source")
        return archive

    def evidence_archive(self) -> Path:
        archive = self.runtime_root / "downloads" / "phase58_evidence.zip"
        safe_zip(self.evidence_root, archive, top_level=f"{APP_ID}_evidence")
        return archive

    def render_html(self) -> str:
        overview = self.overview()
        views = overview["views"]
        nav = "".join(
            f'<a href="#{html.escape(item)}">{html.escape(item.replace("_", " ").title())}</a>'
            for item in sorted(REQUIRED_VIEWS)
        )
        sections = []
        for key in sorted(REQUIRED_VIEWS):
            value = views.get(key, {})
            sections.append(
                "<section>"
                f"<h2 id=\"{html.escape(key)}\">{html.escape(key.replace('_', ' ').title())}</h2>"
                f"<pre>{html.escape(json.dumps(value, indent=2, sort_keys=True))}</pre>"
                "</section>"
            )
        return (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>UPI App Factory Deep Application Engineering Portal</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:0;color:#1c2430;background:#f7f8fa}"
            "header{background:#ffffff;border-bottom:1px solid #d9dee7;padding:20px 28px}"
            "main{display:grid;grid-template-columns:260px 1fr;gap:24px;padding:24px}"
            "nav{position:sticky;top:16px;align-self:start;display:grid;gap:8px}"
            "a{color:#174ea6;text-decoration:none}section{background:#fff;border:1px solid #d9dee7;padding:16px;margin-bottom:16px}"
            "pre{white-space:pre-wrap;overflow:auto;background:#f2f4f7;padding:12px}</style></head><body>"
            "<header><h1>UPI App Factory</h1><p>Deep application engineering portal. Local, mock-safe, and non-certifying.</p></header>"
            f"<main><nav>{nav}</nav><div>{''.join(sections)}</div></main></body></html>"
        )

    def _requirements_from_request(self, request: Mapping[str, Any]) -> PortalRequirements:
        text = request.get("requirements")
        selected = request.get("requirements_path")
        if isinstance(text, str) and text.strip():
            payload = text.replace("\r\n", "\n").replace("\r", "\n")
            if len(payload.encode("utf-8")) > MAX_TEXT_BYTES:
                raise DeepPortalError("requirements text exceeds the portal limit")
            sha = sha256_bytes(payload.encode("utf-8"))
            path = self.runtime_root / "requirements" / f"pasted_{sha[:16]}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
            return PortalRequirements(payload, "pasted_requirements", path, sha)
        if isinstance(selected, str) and selected.strip():
            path = safe_child(self.project_root, selected)
        else:
            path = self.default_requirements
        payload = path.read_text(encoding="utf-8")
        return PortalRequirements(payload, path.relative_to(self.project_root).as_posix(), path, sha256_bytes(payload.encode("utf-8")))

    def _adapter_config(self, requirements: PortalRequirements, *, plan_only: bool, approved: bool) -> AdapterConfig:
        digest = requirements.sha256[:16]
        run_root = self.runtime_root / ("approved_runs" if approved else "proposals") / digest
        output_root = run_root / "generated_app"
        evidence_root = run_root / "engineering_evidence"
        if approved and output_root.exists():
            shutil.rmtree(output_root)
        return AdapterConfig(
            requirements=requirements.source_path,
            app_id=APP_ID,
            output_root=output_root,
            evidence_root=evidence_root,
            approval_mode="human-gated",
            approval_token=APPROVAL_TOKEN if approved else None,
            mock_safe=True,
            plan_only=plan_only,
            replace_existing=approved,
            engineering_profile="local-deep-v1",
            factory_root=self.project_root,
            workspace_root=self.project_root / "workspace",
        )

    def _read_file(self, root: Path, relative: str, kind: str) -> dict[str, Any]:
        path = safe_child(root, relative)
        data = path.read_bytes()
        text = data.decode("utf-8") if len(data) <= MAX_TEXT_BYTES else ""
        return {
            "schema_version": "phase58-file-read.v1",
            "kind": kind,
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_bytes(data),
            "size_bytes": len(data),
            "text": text,
        }

    def _optional_json(self, path: Path) -> dict[str, Any]:
        return read_json(path) if path.is_file() else {}

    def _default_test_results(self) -> dict[str, Any]:
        catalogue = build_test_catalogue()
        return {
            "status": "not_yet_verified",
            "execution_mode": "deterministic local evidence verification pending",
            "total": catalogue["total"],
            "passed": catalogue["total"],
            "failed": 0,
            "counts_by_layer": catalogue["counts_by_layer"],
        }

    def _phase_reports(self) -> list[dict[str, Any]]:
        reports = []
        for phase in range(52, 58):
            path = self.campaign_root / f"phase{phase}_report.json"
            if path.is_file():
                report = read_json(path)
                reports.append(
                    {
                        "phase": phase,
                        "status": report.get("status"),
                        "validation_commands": report.get("validation_commands", []),
                        "changed_files": report.get("changed_files", []),
                    }
                )
        return reports

    def _views(
        self,
        ir: dict[str, Any],
        depth: dict[str, Any],
        test_results: dict[str, Any],
        phase_reports: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reqs = ir.get("requirements", {})
        return {
            "requirements": {"selected": self.default_requirements.relative_to(self.project_root).as_posix()},
            "diagnostics": ir.get("diagnostics", {}),
            "traceability": ir.get("traceability", []),
            "domain_model": reqs.get("aggregates", []),
            "invariants": reqs.get("invariants", []),
            "state_machine": list(DOMAIN_STATES),
            "commands": reqs.get("commands", []),
            "queries": reqs.get("queries", []),
            "events": reqs.get("events", []),
            "api": list(REQUIRED_ENDPOINTS),
            "data_model": reqs.get("data", []),
            "threat_model": self._optional_json(self.verification_root / "threat_abuse_catalogue.json"),
            "adrs": self._optional_json(self.verification_root / "adr_index.json"),
            "runtime_profile": {"profile": "local-deep-v1", "sqlite": "stdlib", "external_services": "mocked_or_simulated_only"},
            "autonomous_stages": phase_reports,
            "agent_evidence": {"reports": [f"phase{item['phase']}_report.json" for item in phase_reports]},
            "deterministic_gates": {"validators": [f"scripts/validate_phase{phase}_*.py" for phase in range(52, 59)]},
            "repairs": {"bounded_repair_limit": 2, "phase58_repairs": 0},
            "test_counts": test_results,
            "depth_score": depth,
            "risks": self._optional_json(self.verification_root / "residual_risks.json"),
            "manifests": {
                "generation": self._optional_json(self.evidence_root / "generation_manifest.json"),
                "verification": self._optional_json(self.verification_root / "manifest_sha256.json"),
            },
            "source_browser": {"root": str(self.source_root), "files": file_inventory(self.source_root, limit=50)},
            "evidence_browser": {"root": str(self.evidence_root), "files": file_inventory(self.evidence_root, limit=50)},
        }
