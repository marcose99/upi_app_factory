from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable

from factory.operator_portal.deep_portal_integration import file_inventory, safe_child
from tools.factory_control_plane.common import default_state_root
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.manifest import CampaignManifest, load_manifest
from tools.factory_control_plane.policy import StandingPolicy
from upi_factory.capstone.phase68 import verify_manifest
from upi_factory.capstone.phase70 import run_phase70_validation


PHASE69_SCHEMA_VERSION = "phase69-control-plane-portal-demonstration.v1"
CAMPAIGN_ID = "phase68_70_consolidated_capstone_v1"
CAMPAIGN_CONFIG = Path("config/control_plane/campaigns/phase68_70_consolidated_capstone.json")
STANDING_POLICY = Path("config/control_plane/standing_policy.json")
RECIPIENT_OUTPUT = Path("factory_governance/phase68_70/recipient_replay_output")
PORTAL_EVIDENCE_ROOT = Path("factory_governance/phase68_70/phase69_control_plane_portal")
PRODUCT_NAME = "UPI App Factory"
CERTIFICATION_POSTURE = "certification-ready-not-certified"
FORBIDDEN_CLAIMS = (
    "production ready",
    "production-ready",
    "officially certified",
    "certified by npci",
    "certified by rbi",
    "real payment calls enabled",
)


class Phase69Error(ValueError):
    """Raised when the Phase 69 demonstration contract fails closed."""


@dataclass(frozen=True)
class PortalFile:
    path: str
    sha256: str
    bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "bytes": self.bytes}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _compact_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Phase69Error(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _file_record(path: Path, root: Path) -> PortalFile:
    if not path.is_file() or path.is_symlink():
        raise Phase69Error(f"Unsafe or missing portal file: {path}")
    return PortalFile(path=_relative(path, root), sha256=_hash_file(path), bytes=path.stat().st_size)


def _query_rows(db_path: Path, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    with sqlite3.connect(str(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql, params).fetchall()
    return [{str(key): row[key] for key in row.keys()} for row in rows]


def _policy_decisions(db_path: Path, campaign_id: str) -> list[dict[str, Any]]:
    rows = _query_rows(
        db_path,
        "SELECT activity_id, decision_json FROM policy_decisions WHERE campaign_id=? ORDER BY rowid",
        (campaign_id,),
    )
    decisions: list[dict[str, Any]] = []
    for row in rows:
        decision = json.loads(str(row["decision_json"]))
        if isinstance(decision, dict):
            decisions.append({"activity_id": row["activity_id"], **decision})
    return decisions


def _activities(db_path: Path, campaign_id: str) -> list[dict[str, Any]]:
    rows = _query_rows(
        db_path,
        "SELECT activity_id, status, result_json FROM activities WHERE campaign_id=? ORDER BY rowid",
        (campaign_id,),
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["result_json"])) if row["result_json"] else {}
        result.append(
            {
                "activity_id": str(row["activity_id"]),
                "status": str(row["status"]),
                "returncode": payload.get("returncode"),
                "stdout_sha256": payload.get("stdout_sha256"),
                "stderr_sha256": payload.get("stderr_sha256"),
            }
        )
    return result


def _incidents(db_path: Path, campaign_id: str) -> list[dict[str, Any]]:
    rows = _query_rows(
        db_path,
        "SELECT incident_id, activity_id, failure_class, payload_json FROM incidents WHERE campaign_id=? ORDER BY rowid",
        (campaign_id,),
    )
    incidents: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        incidents.append(
            {
                "incident_id": str(row["incident_id"]),
                "activity_id": row["activity_id"],
                "failure_class": str(row["failure_class"]),
                "payload_sha256": _sha256_bytes(_compact_json(payload)),
            }
        )
    return incidents


def _events(db_path: Path, campaign_id: str) -> list[dict[str, Any]]:
    rows = _query_rows(
        db_path,
        "SELECT event_hash, sequence, event_type, payload_json, created_at FROM events WHERE campaign_id=? ORDER BY sequence",
        (campaign_id,),
    )
    events: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        events.append(
            {
                "event_hash": str(row["event_hash"]),
                "sequence": int(row["sequence"]),
                "event_type": str(row["event_type"]),
                "payload": payload,
                "created_at": str(row["created_at"]),
            }
        )
    return events


def _manifest_activity_rows(manifest: CampaignManifest) -> list[dict[str, Any]]:
    return [
        {
            "activity_id": activity.id,
            "action": activity.action,
            "kind": activity.kind,
            "risk": activity.risk,
            "target_state": activity.target_state.value,
            "dependencies": list(activity.dependencies),
            "digest": activity.digest,
        }
        for activity in manifest.activities
    ]


def _activity_state(manifest: CampaignManifest, observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["activity_id"]: item for item in observed}
    rows: list[dict[str, Any]] = []
    for item in _manifest_activity_rows(manifest):
        observed_item = by_id.get(item["activity_id"])
        rows.append({**item, "status": "pending" if observed_item is None else observed_item["status"], "result": observed_item})
    return rows


def _kpis(manifest: CampaignManifest, activities: list[dict[str, Any]], incidents: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(manifest.activities)
    completed = sum(1 for item in activities if item["status"] == "completed")
    completion_percent = 0 if total == 0 else round((completed / total) * 100, 2)
    return {
        "total_activities": total,
        "completed_activities": completed,
        "completion_percent": completion_percent,
        "incident_count": len(incidents),
        "blocked": any(item["status"] == "failed" for item in activities) or bool(incidents),
    }


def _checkpoint_state(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    checkpoints: list[dict[str, Any]] = []
    for event in events:
        if event["event_type"] == "state_transition":
            payload = event.get("payload", {})
            checkpoints.append(
                {
                    "sequence": event["sequence"],
                    "from": payload.get("from"),
                    "to": payload.get("to"),
                    "event_hash": event["event_hash"],
                }
            )
    return checkpoints


def _human_gates(policy: StandingPolicy, manifest: CampaignManifest, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configured = manifest.raw.get("approvals", {}).get("human", [])
    gates: list[dict[str, Any]] = [
        {
            "action": str(action),
            "source": "campaign_manifest",
            "status": "not_requested",
        }
        for action in configured
        if isinstance(action, str)
    ]
    for action in sorted(policy.human_actions):
        gates.append({"action": action, "source": "standing_policy", "status": "human_required"})
    for decision in decisions:
        if decision.get("human_required") is True:
            gates.append(
                {
                    "action": decision.get("action"),
                    "source": "control_plane_decision",
                    "status": "paused",
                    "decision_id": decision.get("decision_id"),
                }
            )
    return gates


def _repair_budget_decisions(manifest: CampaignManifest, incidents: list[dict[str, Any]]) -> dict[str, Any]:
    budget = int(manifest.budgets.get("engineering_repairs", 0))
    consuming = [item for item in incidents if item["failure_class"] == "PRODUCT_DEFECT"]
    return {
        "budget": budget,
        "consumed": len(consuming),
        "remaining": max(0, budget - len(consuming)),
        "decisions": [
            {
                "incident_id": item["incident_id"],
                "failure_class": item["failure_class"],
                "consumes_repair_budget": item["failure_class"] == "PRODUCT_DEFECT",
            }
            for item in incidents
        ],
    }


def _evidence_integrity(project_root: Path, state_root: Path, campaign_id: str, portal_records: list[PortalFile]) -> dict[str, Any]:
    campaign_evidence = state_root / "evidence" / campaign_id
    sealed = state_root / "sealed" / f"{campaign_id}.seal.json"
    records = [record.as_dict() for record in portal_records]
    if campaign_evidence.is_dir():
        for path in sorted(campaign_evidence.rglob("*")):
            if path.is_file() and not path.is_symlink():
                records.append(_file_record(path, state_root).as_dict())
    if sealed.is_file():
        records.append(_file_record(sealed, state_root).as_dict())
    return {
        "status": "verified" if records else "missing",
        "record_count": len(records),
        "records": records,
        "sealed_evidence": str(sealed) if sealed.is_file() else None,
        "source_root": _relative(campaign_evidence, project_root) if campaign_evidence.exists() else None,
    }


def _recipient_download(project_root: Path) -> dict[str, Any]:
    output = project_root / RECIPIENT_OUTPUT
    manifest_path = output / "content_manifest.json"
    if not manifest_path.is_file():
        return {
            "status": "missing",
            "content_manifest": _relative(manifest_path, project_root),
            "content_manifest_sha256": None,
            "download_path": _relative(output / "handoff_bundle.zip", project_root),
            "download_sha256": None,
            "download_bytes": 0,
            "replay_result": None,
        }
    verification = verify_manifest(manifest_path)
    result_path = output / "recipient_replay_result.json"
    result = _read_json(result_path) if result_path.is_file() else {}
    bundle = output / "handoff_bundle.zip"
    return {
        "status": verification["status"],
        "content_manifest": _relative(manifest_path, project_root),
        "content_manifest_sha256": verification["manifest_sha256"],
        "download_path": _relative(bundle, project_root),
        "download_sha256": _hash_file(bundle),
        "download_bytes": bundle.stat().st_size,
        "replay_result": result,
    }


def _portfolio(project_root: Path) -> dict[str, Any]:
    validation = run_phase70_validation(project_root=project_root)
    return {
        "status": validation["status"],
        "profile_count": validation["profile_count"],
        "profiles": [
            {
                "app_id": item["profile_id"],
                "title": item["title"],
                "depth_score": item["depth_score"],
                "stable_profile_sha256": item["stable_profile_sha256"],
            }
            for item in validation["profiles"]
        ],
        "validation": validation,
    }


def _safe_browsing(project_root: Path, state_root: Path, campaign_id: str) -> dict[str, Any]:
    return {
        "source_browser": {
            "root": "src/upi_factory/capstone",
            "files": file_inventory(project_root / "src/upi_factory/capstone", limit=100),
        },
        "portal_browser": {
            "root": "factory/operator_portal",
            "files": file_inventory(project_root / "factory/operator_portal", limit=150),
        },
        "evidence_browser": {
            "root": str(state_root / "evidence" / campaign_id),
            "files": file_inventory(state_root / "evidence" / campaign_id, limit=150),
        },
        "openapi": {
            "path": "/openapi.json",
            "capstone_portal_paths": [
                "/operator-portal/api/capstone/phase69/status",
                "/operator-portal/api/capstone/phase69/demonstration",
                "/operator-portal/api/capstone/phase69/source",
                "/operator-portal/api/capstone/phase69/evidence",
            ],
        },
    }


def build_phase69_status(
    *,
    project_root: Path | None = None,
    state_root: Path | None = None,
    campaign_config: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or repository_root()).resolve()
    state = (state_root or default_state_root()).resolve()
    manifest_path = (campaign_config or root / CAMPAIGN_CONFIG).resolve()
    manifest = load_manifest(manifest_path, root)
    policy = StandingPolicy(root / STANDING_POLICY)
    db_path = state / "control_plane.sqlite3"
    events = _events(db_path, manifest.campaign_id)
    observed_activities = _activities(db_path, manifest.campaign_id)
    incidents = _incidents(db_path, manifest.campaign_id)
    decisions = _policy_decisions(db_path, manifest.campaign_id)
    activity_state = _activity_state(manifest, observed_activities)
    kpis = _kpis(manifest, activity_state, incidents)
    recipient = _recipient_download(root)
    portfolio = _portfolio(root)
    portal_records = [
        _file_record(root / "docs/capstone/phase68_70/phase69_control_plane_operator_portal_demonstration.md", root),
        _file_record(root / "scripts/validate_phase69_control_plane_portal_demonstration.py", root),
        _file_record(manifest_path, root),
    ]
    status = "complete" if kpis["completion_percent"] == 100 and not kpis["blocked"] else "in_progress"
    if not events:
        status = "not_started"
    result = {
        "schema_version": PHASE69_SCHEMA_VERSION,
        "phase": "69",
        "product_name": PRODUCT_NAME,
        "repository_id": "upi_app_factory",
        "campaign_id": manifest.campaign_id,
        "status": status,
        "certification_posture": CERTIFICATION_POSTURE,
        "official_certification_claimed": False,
        "production_readiness_claimed": False,
        "real_payment_calls": "disabled",
        "live_external_integrations": "disabled",
        "runtime_llm_calls_default": 0,
        "campaign_manifest": {
            "path": _relative(manifest_path, root),
            "sha256": manifest.digest,
            "baseline": manifest.baseline,
            "objective": manifest.objective,
            "scope": manifest.scope,
            "budgets": manifest.budgets,
        },
        "control_plane": {
            "source_of_truth": True,
            "state_root": str(state),
            "database": str(db_path),
            "event_count": len(events),
            "events": events,
        },
        "requirements_intake": {
            "status": recipient["status"],
            "artifact": "factory_governance/phase68_70/recipient_fixture/requirements_intake.json",
        },
        "policy_decisions": decisions,
        "dependency_activity_state": activity_state,
        "checkpoints": _checkpoint_state(events),
        "incidents": incidents,
        "repair_budget_decisions": _repair_budget_decisions(manifest, incidents),
        "human_gates": _human_gates(policy, manifest, decisions),
        "kpis": kpis,
        "evidence_integrity": _evidence_integrity(root, state, manifest.campaign_id, portal_records),
        "recipient_download": recipient,
        "generated_application_portfolio": portfolio,
        "safe_browsing": _safe_browsing(root, state, manifest.campaign_id),
    }
    _assert_no_forbidden_claims(result)
    return result


def run_phase69_demonstration(
    *,
    project_root: Path | None = None,
    state_root: Path | None = None,
    campaign_config: Path | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    root = (project_root or repository_root()).resolve()
    state = (state_root or default_state_root()).resolve()
    manifest_path = (campaign_config or root / CAMPAIGN_CONFIG).resolve()
    engine = ControlPlaneEngine(root, state, root / STANDING_POLICY)
    try:
        run_result = engine.run(manifest_path)
    finally:
        engine.close()
    status = build_phase69_status(project_root=root, state_root=state, campaign_config=manifest_path)
    result = {
        "schema_version": PHASE69_SCHEMA_VERSION,
        "status": "PASS" if run_result.get("status") == "closed" and status["status"] == "complete" else "FAIL",
        "control_plane_run": run_result,
        "portal": status,
    }
    result["demonstration_sha256"] = _sha256_bytes(_compact_json(result))
    if write_evidence:
        evidence_path = root / PORTAL_EVIDENCE_ROOT / "phase69_demonstration.json"
        _write_json(evidence_path, result)
    _assert_no_forbidden_claims(result)
    return result


def _assert_no_forbidden_claims(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for phrase in FORBIDDEN_CLAIMS:
        if phrase in text:
            raise Phase69Error(f"Forbidden claim found: {phrase}")


def read_safe_source(project_root: Path, relative: str) -> dict[str, Any]:
    root = project_root.resolve()
    allowed_roots = [
        root / "src/upi_factory/capstone",
        root / "factory/operator_portal",
        root / "docs/capstone/phase68_70",
    ]
    for allowed in allowed_roots:
        try:
            path = safe_child(allowed, relative)
            data = path.read_bytes()
            return {
                "status": "available",
                "root": _relative(allowed, root),
                "path": path.relative_to(allowed).as_posix(),
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
                "text": data[:128 * 1024].decode("utf-8", errors="replace"),
            }
        except Exception:
            continue
    raise Phase69Error("source path is outside the safe capstone portal browsing roots")


def read_safe_evidence(state_root: Path, campaign_id: str, relative: str) -> dict[str, Any]:
    evidence_root = state_root.resolve() / "evidence" / campaign_id
    path = safe_child(evidence_root, relative)
    data = path.read_bytes()
    return {
        "status": "available",
        "root": str(evidence_root),
        "path": path.relative_to(evidence_root).as_posix(),
        "sha256": _sha256_bytes(data),
        "bytes": len(data),
        "text": data[:128 * 1024].decode("utf-8", errors="replace"),
    }


def render_phase69_view(status: dict[str, Any]) -> str:
    activities = "\n".join(
        "<tr>"
        f"<td>{escape(str(item['activity_id']))}</td>"
        f"<td>{escape(str(item['status']))}</td>"
        f"<td>{escape(str(item['risk']))}</td>"
        f"<td>{escape(str(item['target_state']))}</td>"
        "</tr>"
        for item in status["dependency_activity_state"]
    )
    profiles = "\n".join(
        "<li>"
        f"<strong>{escape(str(item['title']))}</strong> "
        f"<span>{escape(str(item['app_id']))}</span> "
        f"<code>{escape(str(item['stable_profile_sha256']))}</code>"
        "</li>"
        for item in status["generated_application_portfolio"]["profiles"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UPI App Factory Capstone Control Plane</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; background: Canvas; color: CanvasText; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    section {{ border-top: 1px solid color-mix(in srgb, CanvasText 20%, transparent); padding: 18px 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .metric {{ border: 1px solid color-mix(in srgb, CanvasText 18%, transparent); border-radius: 8px; padding: 12px; }}
    .metric span {{ display: block; font-size: 0.85rem; opacity: 0.75; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; border-bottom: 1px solid color-mix(in srgb, CanvasText 15%, transparent); padding: 8px; }}
    code {{ overflow-wrap: anywhere; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto; }} }}
  </style>
</head>
<body>
<main>
  <h1>UPI App Factory Control Plane Campaign</h1>
  <p>Local-only, fictional-data-only, certification-ready-not-certified.</p>
  <section class="grid" aria-label="Campaign metrics">
    <div class="metric"><span>Status</span><strong>{escape(str(status["status"]))}</strong></div>
    <div class="metric"><span>Completion</span><strong>{escape(str(status["kpis"]["completion_percent"]))}%</strong></div>
    <div class="metric"><span>Evidence Records</span><strong>{escape(str(status["evidence_integrity"]["record_count"]))}</strong></div>
    <div class="metric"><span>Portfolio Apps</span><strong>{escape(str(status["generated_application_portfolio"]["profile_count"]))}</strong></div>
  </section>
  <section>
    <h2>Activity State</h2>
    <table><thead><tr><th>Activity</th><th>Status</th><th>Risk</th><th>Checkpoint</th></tr></thead><tbody>{activities}</tbody></table>
  </section>
  <section>
    <h2>Portfolio</h2>
    <ul>{profiles}</ul>
  </section>
  <section>
    <h2>Downloads</h2>
    <a href="/operator-portal/api/capstone/phase69/downloads/recipient">Recipient application bundle</a>
  </section>
</main>
</body>
</html>
"""


def validate_phase69_demonstration(*, project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or repository_root()).resolve()
    with tempfile.TemporaryDirectory(prefix="upi_phase69_control_plane_") as temporary:
        state_root = Path(temporary)
        result = run_phase69_demonstration(project_root=root, state_root=state_root, write_evidence=False)
    portal = result["portal"]
    errors: list[str] = []
    if result["status"] != "PASS":
        errors.append("control-plane demonstration did not close")
    if portal["control_plane"]["source_of_truth"] is not True or portal["control_plane"]["event_count"] == 0:
        errors.append("portal status is not backed by control-plane events")
    if portal["kpis"]["completion_percent"] != 100:
        errors.append("completion KPI does not derive to 100 percent from completed activities")
    if portal["recipient_download"]["status"] != "PASS":
        errors.append("Phase 68 recipient download is not verified")
    if portal["generated_application_portfolio"]["status"] != "PASS" or portal["generated_application_portfolio"]["profile_count"] != 6:
        errors.append("Phase 70 portfolio is not integrated")
    if portal["evidence_integrity"]["record_count"] < 3:
        errors.append("evidence integrity records are incomplete")
    if not portal["safe_browsing"]["openapi"]["capstone_portal_paths"]:
        errors.append("OpenAPI discovery paths are missing")
    if portal["official_certification_claimed"] or portal["production_readiness_claimed"]:
        errors.append("unsupported certification or production claim detected")
    status = "PASS" if not errors else "FAIL"
    return {
        "schema_version": PHASE69_SCHEMA_VERSION,
        "status": status,
        "errors": errors,
        "campaign_id": portal["campaign_id"],
        "demonstration_sha256": result["demonstration_sha256"],
        "checked_contracts": [
            "control_plane_source_of_truth",
            "phase68_recipient_download",
            "phase70_multi_domain_portfolio",
            "evidence_backed_kpis",
            "safe_browsing_openapi",
            "mock_only_certification_boundary",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or validate the Phase 69 control-plane portal demonstration.")
    parser.add_argument("--project-root", type=Path, default=repository_root())
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.validate_only or args.state_root is None:
            result = validate_phase69_demonstration(project_root=args.project_root)
        else:
            result = run_phase69_demonstration(project_root=args.project_root, state_root=args.state_root)
    except Exception as exc:
        print(_canonical_json({"schema_version": PHASE69_SCHEMA_VERSION, "status": "FAIL", "error": str(exc)}), end="")
        return 1
    print(_canonical_json(result), end="")
    return 0 if result.get("status") == "PASS" else 1
