from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from tools.factory_control_plane.common import (
    DEFAULT_BASELINE,
    ControlPlaneError,
    git_head,
)
from tools.factory_control_plane.evidence import (
    campaign_evidence_dir,
    seal_directory,
    write_activity_envelope,
    write_control_envelope,
    write_summary,
)
from tools.factory_control_plane.executor import CapabilityExecutor
from tools.factory_control_plane.failures import FailureClass, consumes_repair_budget
from tools.factory_control_plane.lifecycle import LifecycleState
from tools.factory_control_plane.manifest import Activity, CampaignManifest, load_manifest
from tools.factory_control_plane.policy import StandingPolicy
from tools.factory_control_plane.state import StateStore


class ControlPlaneEngine:
    def __init__(self, project_root: Path, state_root: Path, policy_path: Path) -> None:
        self.project_root = project_root.resolve()
        self.state_root = state_root.resolve()
        self.policy = StandingPolicy(policy_path)
        self.store = StateStore(self.state_root / "control_plane.sqlite3")
        self.executor = CapabilityExecutor(self.project_root)

    def close(self) -> None:
        self.store.close()

    def validate(self, manifest_path: Path) -> CampaignManifest:
        return load_manifest(manifest_path, self.project_root)

    def run(self, manifest_path: Path) -> dict[str, Any]:
        manifest = self.validate(manifest_path)
        baseline = self._resolve_baseline(manifest)
        state = self.store.create_or_load_campaign(manifest, baseline)
        if state is LifecycleState.CLOSED:
            return self._finish(manifest)
        reconciled = self._reconcile_runtime_noise(manifest)
        hydrated = self._hydrate_prerequisites(manifest)
        if hydrated["failure_class"] is not None:
            failure_class = str(hydrated["failure_class"])
            self.store.record_incident(
                manifest.campaign_id,
                None,
                failure_class,
                hydrated,
            )
            return {
                "status": "failed",
                "campaign_id": manifest.campaign_id,
                "failure_class": failure_class,
                "classification": hydrated,
            }
        self.store.set_state(manifest.campaign_id, LifecycleState.INTAKE_VALIDATED)
        self.store.set_state(manifest.campaign_id, LifecycleState.RISK_CLASSIFIED)
        self.store.set_state(manifest.campaign_id, LifecycleState.PLAN_APPROVED_BY_POLICY)
        write_control_envelope(
            self.state_root,
            manifest.campaign_id,
            "execution_order",
            {
                "order": [
                    "reconcile",
                    "hydrate",
                    "baseline_observe",
                    "candidate_observe",
                    "classify",
                    "repair_when_attributable",
                    "revalidate",
                    "seal",
                ],
                "reconcile": reconciled,
                "hydrate": hydrated,
            },
        )
        completed: set[str] = {
            activity.id
            for activity in manifest.activities
            if (
                self.store.activity_status(manifest.campaign_id, activity)[0]
                == "completed"
            )
        }
        while len(completed) < len(manifest.activities):
            ready = [
                activity
                for activity in manifest.activities
                if activity.id not in completed
                and all(dep in completed for dep in activity.dependencies)
            ]
            if not ready:
                raise ControlPlaneError("no topological activity is ready")
            activity = ready[0]
            status, existing = self.store.activity_status(manifest.campaign_id, activity)
            if status == "completed" and existing is not None:
                completed.add(activity.id)
                continue
            decision = self.policy.evaluate(activity.action, activity.risk)
            self.store.record_policy(manifest.campaign_id, activity.id, decision.to_record())
            if decision.outcome == "pause":
                return {
                    "status": "human_gate",
                    "campaign_id": manifest.campaign_id,
                    "decision": decision.to_record(),
                }
            if decision.outcome == "deny":
                self.store.record_incident(
                    manifest.campaign_id,
                    activity.id,
                    FailureClass.POLICY_DENIAL.value,
                    {"decision": decision.to_record()},
                )
                return {
                    "status": "failed",
                    "campaign_id": manifest.campaign_id,
                    "failure_class": FailureClass.POLICY_DENIAL.value,
                }
            if activity.kind == "verification":
                observed = self._observe_and_classify(manifest, activity, baseline, decision.to_record())
                if observed["failure_class"] is not None:
                    failure_class = str(observed["failure_class"])
                    self.store.record_activity(
                        manifest.campaign_id,
                        activity,
                        "failed",
                        observed["candidate_result"],
                    )
                    self.store.record_incident(
                        manifest.campaign_id,
                        activity.id,
                        failure_class,
                        observed,
                    )
                    return {
                        "status": "failed",
                        "campaign_id": manifest.campaign_id,
                        "failure_class": failure_class,
                        "consumes_repair_budget": bool(
                            observed["consumes_repair_budget"]
                        ),
                        "classification": observed,
                    }
                result = observed["candidate_result"]
            else:
                result = self.executor.run(activity).to_record()
            envelope = {
                "activity": _activity_record(activity),
                "result": result,
                "policy": decision.to_record(),
            }
            write_activity_envelope(self.state_root, manifest.campaign_id, activity.id, envelope)
            if result["returncode"] != 0:
                self.store.record_activity(manifest.campaign_id, activity, "failed", result)
                self.store.record_incident(
                    manifest.campaign_id,
                    activity.id,
                    FailureClass.PRODUCT_DEFECT.value,
                    {"returncode": result["returncode"], "stderr_sha256": result["stderr_sha256"]},
                )
                return {
                    "status": "failed",
                    "campaign_id": manifest.campaign_id,
                    "failure_class": FailureClass.PRODUCT_DEFECT.value,
                    "consumes_repair_budget": True,
                }
            self.store.record_activity(manifest.campaign_id, activity, "completed", result)
            self.store.set_state(manifest.campaign_id, activity.target_state)
            completed.add(activity.id)
        self.store.set_state(manifest.campaign_id, LifecycleState.CLOSED)
        return self._finish(manifest)

    def status(self, campaign_id: str) -> dict[str, Any]:
        return self.store.summary(campaign_id)

    def seal_evidence(self, campaign_id: str) -> dict[str, str]:
        root = campaign_evidence_dir(self.state_root, campaign_id)
        return seal_directory(root, self.state_root / "sealed")

    def _finish(self, manifest: CampaignManifest) -> dict[str, Any]:
        write_summary(self.state_root, self.store, manifest.campaign_id)
        sealed = self.seal_evidence(manifest.campaign_id)
        return {
            "status": "closed",
            "campaign_id": manifest.campaign_id,
            "summary": self.store.summary(manifest.campaign_id),
            "sealed": sealed,
        }

    def _resolve_baseline(self, manifest: CampaignManifest) -> str:
        if manifest.baseline == "HEAD":
            return git_head(self.project_root)
        if manifest.baseline == "BASELINE_COMMIT":
            return DEFAULT_BASELINE
        return manifest.baseline

    def _reconcile_runtime_noise(self, manifest: CampaignManifest) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for item in manifest.validation_controls.deterministic_runtime_noise:
            path = (self.project_root / item.path).resolve()
            existed = path.exists()
            removed = False
            if existed:
                if item.kind == "directory":
                    if not path.is_dir():
                        raise ControlPlaneError(
                            f"deterministic runtime noise kind mismatch: {item.path}"
                        )
                    shutil.rmtree(path)
                    removed = True
                else:
                    if not path.is_file():
                        raise ControlPlaneError(
                            f"deterministic runtime noise kind mismatch: {item.path}"
                        )
                    path.unlink()
                    removed = True
            entries.append(
                {
                    "id": item.id,
                    "kind": item.kind,
                    "path": item.path,
                    "existed": existed,
                    "removed": removed,
                    "digest": item.digest,
                }
            )
        payload = {
            "phase": "reconcile",
            "failure_class": None,
            "runtime_noise": entries,
        }
        write_control_envelope(self.state_root, manifest.campaign_id, "reconcile", payload)
        return payload

    def _hydrate_prerequisites(self, manifest: CampaignManifest) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        missing: list[str] = []
        for item in manifest.validation_controls.trusted_prerequisites:
            path = (self.project_root / item.path).resolve()
            existed_before = path.exists()
            if not existed_before and item.hydrate and item.kind == "directory":
                path.mkdir(parents=True, exist_ok=True)
            exists_after = path.exists()
            kind_matches = (
                (item.kind == "directory" and path.is_dir())
                or (item.kind == "file" and path.is_file())
            )
            if not exists_after or not kind_matches:
                missing.append(item.id)
            entries.append(
                {
                    "id": item.id,
                    "kind": item.kind,
                    "path": item.path,
                    "hydrate": item.hydrate,
                    "existed_before": existed_before,
                    "exists_after": exists_after,
                    "kind_matches": kind_matches,
                    "digest": item.digest,
                }
            )
        failure_class = FailureClass.MISSING_PREREQUISITE.value if missing else None
        payload = {
            "phase": "hydrate",
            "failure_class": failure_class,
            "missing": missing,
            "trusted_prerequisites": entries,
        }
        write_control_envelope(self.state_root, manifest.campaign_id, "hydrate", payload)
        return payload

    def _observe_and_classify(
        self,
        manifest: CampaignManifest,
        activity: Activity,
        baseline: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        baseline_result = self.executor.observe(activity, "baseline", baseline).to_record()
        candidate_result = self.executor.observe(activity, "candidate", "WORKTREE").to_record()
        failure_class = self._classify_observation(baseline_result, candidate_result)
        payload = {
            "phase": "classify",
            "activity": _activity_record(activity),
            "baseline": baseline,
            "baseline_result": baseline_result,
            "candidate_result": candidate_result,
            "failure_class": None if failure_class is None else failure_class.value,
            "consumes_repair_budget": (
                False if failure_class is None else consumes_repair_budget(failure_class)
            ),
            "policy": policy,
        }
        write_control_envelope(
            self.state_root,
            manifest.campaign_id,
            f"classification_{activity.id}",
            payload,
        )
        return payload

    def _classify_observation(
        self,
        baseline: dict[str, Any],
        candidate: dict[str, Any],
    ) -> FailureClass | None:
        if int(candidate["returncode"]) == 0:
            return None
        marker = _failure_marker(str(candidate["stdout"]) + "\n" + str(candidate["stderr"]))
        if marker is not None:
            return marker
        if int(baseline["returncode"]) != 0 and _result_signature(baseline) == _result_signature(candidate):
            return FailureClass.BASELINE_DEFECT
        if int(baseline["returncode"]) != 0:
            return FailureClass.TEST_DEFECT
        return FailureClass.PRODUCT_DEFECT


def _activity_record(activity: Activity) -> dict[str, Any]:
    return {
        "id": activity.id,
        "action": activity.action,
        "kind": activity.kind,
        "risk": activity.risk,
        "target_state": activity.target_state.value,
        "digest": activity.digest,
    }


def _result_signature(result: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(result["returncode"]),
        str(result["stdout_sha256"]),
        str(result["stderr_sha256"]),
    )


def _failure_marker(output: str) -> FailureClass | None:
    prefix = "CONTROL_PLANE_FAILURE_CLASS="
    allowed = {
        FailureClass.PRODUCT_DEFECT,
        FailureClass.TEST_DEFECT,
        FailureClass.MISSING_PREREQUISITE,
        FailureClass.NON_HERMETIC_TEST,
        FailureClass.BASELINE_DEFECT,
        FailureClass.CONTROLLER_DEFECT,
        FailureClass.EVIDENCE_INTEGRITY_FAILURE,
    }
    for line in output.splitlines():
        if line.startswith(prefix):
            try:
                marker = FailureClass(line[len(prefix) :].strip())
            except ValueError:
                return FailureClass.CONTROLLER_DEFECT
            return marker if marker in allowed else FailureClass.CONTROLLER_DEFECT
    return None
