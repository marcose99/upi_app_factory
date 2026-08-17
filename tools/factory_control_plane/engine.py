from __future__ import annotations

from pathlib import Path
import io
import json
import subprocess
import tarfile
import tempfile
from typing import Any

from tools.factory_control_plane.common import (
    DEFAULT_BASELINE,
    ControlPlaneError,
    git_head,
    git_worktree_identity,
)
from tools.factory_control_plane.evidence import (
    campaign_evidence_dir,
    seal_directory,
    snapshot_manifest,
    verify_seal,
    write_activity_envelope,
    write_control_envelope,
    write_summary,
)
from tools.factory_control_plane.executor import CapabilityExecutor
from tools.factory_control_plane.failures import FailureClass, consumes_repair_budget
from tools.factory_control_plane.lifecycle import LifecycleState, STATE_INDEX
from tools.factory_control_plane.manifest import Activity, CampaignManifest, load_manifest
from tools.factory_control_plane.policy import StandingPolicy
from tools.factory_control_plane.state import StateStore


class ControlPlaneEngine:
    def __init__(self, project_root: Path, state_root: Path, policy_path: Path) -> None:
        self.project_root = project_root.resolve()
        self.state_root = state_root.resolve()
        # Bind every authority object opened below to the exact candidate from
        # which it was loaded. A checkout pathname substitution must not let a
        # later run qualify different bytes using retained old descriptors.
        self._authority_candidate_identity = git_worktree_identity(self.project_root)
        self.policy = StandingPolicy(policy_path)
        self.store = StateStore(self.state_root / "control_plane.sqlite3")
        self.executor = CapabilityExecutor(self.project_root)

    def close(self) -> None:
        self.executor.close()
        self.store.close()

    def validate(self, manifest_path: Path) -> CampaignManifest:
        return load_manifest(manifest_path, self.project_root)

    def run(self, manifest_path: Path) -> dict[str, Any]:
        if git_worktree_identity(self.project_root) != self._authority_candidate_identity:
            raise ControlPlaneError(
                "candidate identity drifted after authority descriptors were loaded"
            )
        manifest = self.validate(manifest_path)
        preflight = self._authorize_before_mutation(manifest)
        if preflight is not None:
            return preflight
        baseline = self._resolve_baseline(manifest)
        candidate_identity = git_worktree_identity(self.project_root)
        state = self.store.create_or_load_campaign(manifest, baseline)
        if state in {LifecycleState.FINALIZING, LifecycleState.CLOSED}:
            return self._finish(manifest, candidate_identity, already_closed=True)
        completed_before_resume = self.store.completed_activity_ids(manifest.campaign_id)
        if completed_before_resume:
            last_completed = next(
                activity
                for activity in reversed(manifest.activities)
                if activity.id in completed_before_resume
            )
            identity_path = campaign_evidence_dir(
                self.state_root, manifest.campaign_id
            ) / f"control/activity_candidate_identity_{last_completed.id}.json"
            try:
                resumed_identity = json.loads(identity_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ControlPlaneError(
                    "resumed campaign has no valid completed-activity candidate binding"
                ) from exc
            if resumed_identity != candidate_identity:
                raise ControlPlaneError("resumed campaign candidate identity drifted")
        reconciled = (
            self._resume_without_runtime_noise_reconciliation(manifest)
            if completed_before_resume
            else self._reconcile_runtime_noise(manifest)
        )
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
        candidate_identity = git_worktree_identity(self.project_root)
        write_control_envelope(
            self.state_root, manifest.campaign_id, "candidate_identity", candidate_identity
        )
        for initialization_state in (
            LifecycleState.INTAKE_VALIDATED,
            LifecycleState.RISK_CLASSIFIED,
            LifecycleState.PLAN_APPROVED_BY_POLICY,
        ):
            if STATE_INDEX[self.store.lifecycle_state(manifest.campaign_id)] < STATE_INDEX[initialization_state]:
                self.store.set_state(manifest.campaign_id, initialization_state)
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
                "expected_activities": [activity.id for activity in manifest.activities],
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
                observed = self._observe_and_classify(
                    manifest, activity, baseline, decision.to_record(), candidate_identity
                )
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
                if git_worktree_identity(self.project_root) != candidate_identity:
                    raise ControlPlaneError(
                        "candidate identity drifted before capability execution"
                    )
                if isinstance(self.executor, CapabilityExecutor):
                    result = self.executor.run(
                        activity, expected_identity=candidate_identity
                    ).to_record()
                else:
                    # Deterministic test doubles do not materialize or execute bytes.
                    result = self.executor.run(activity).to_record()
                candidate_identity = git_worktree_identity(self.project_root)
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
            write_control_envelope(
                self.state_root,
                manifest.campaign_id,
                f"activity_candidate_identity_{activity.id}",
                candidate_identity,
            )
            self.store.record_activity(manifest.campaign_id, activity, "completed", result)
            if STATE_INDEX[self.store.lifecycle_state(manifest.campaign_id)] < STATE_INDEX[activity.target_state]:
                self.store.set_state(manifest.campaign_id, activity.target_state)
            completed.add(activity.id)
        # Bind finalization to the exact candidate before making the durable
        # lifecycle transition.  A FINALIZING resume without this record must
        # fail closed rather than blessing whatever tree happens to be present.
        write_control_envelope(
            self.state_root,
            manifest.campaign_id,
            "final_candidate_identity",
            candidate_identity,
        )
        self.store.set_state(manifest.campaign_id, LifecycleState.FINALIZING)
        return self._finish(manifest, candidate_identity)

    def status(self, campaign_id: str) -> dict[str, Any]:
        summary = self.store.summary(campaign_id)
        if summary["state"] == LifecycleState.CLOSED.value:
            self._verified_existing_seal(campaign_id)
        return summary

    def seal_evidence(self, campaign_id: str) -> dict[str, str]:
        summary = self.store.summary(campaign_id)
        if summary["state"] != LifecycleState.FINALIZING.value:
            raise ControlPlaneError("only a FINALIZING campaign can be sealed")
        root = campaign_evidence_dir(self.state_root, campaign_id)
        execution_order_path = root / "control/execution_order.json"
        final_identity_path = root / "control/final_candidate_identity.json"
        summary_path = root / "summary.json"
        try:
            execution_order = json.loads(execution_order_path.read_text(encoding="utf-8"))
            final_identity = json.loads(final_identity_path.read_text(encoding="utf-8"))
            evidence_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlPlaneError("campaign evidence is incomplete or invalid") from exc
        expected = execution_order.get("expected_activities")
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            raise ControlPlaneError("campaign evidence has no valid expected activity set")
        if self.store.completed_activity_ids(campaign_id) != set(expected):
            raise ControlPlaneError("campaign activities are incomplete")
        if final_identity != git_worktree_identity(self.project_root):
            raise ControlPlaneError("sealed candidate identity does not match the current candidate")
        if evidence_summary != {
            "summary": summary,
            "events": self.store.export_events(campaign_id),
        }:
            raise ControlPlaneError("campaign summary evidence does not match durable state")
        if self._seal_exists(campaign_id):
            sealed = self._verified_existing_seal(campaign_id)
            sealed_manifest = Path(sealed["manifest"])
            current_manifest = snapshot_manifest(root)
            if json.loads(sealed_manifest.read_text(encoding="utf-8")) != current_manifest:
                raise ControlPlaneError("published seal does not match current campaign evidence")
            return sealed
        return seal_directory(
            root,
            self.state_root / "sealed",
            self.state_root.parent / f".{self.state_root.name}-evidence-trust-anchors",
        )

    def _finish(
        self,
        manifest: CampaignManifest,
        candidate_identity: dict[str, str],
        already_closed: bool = False,
    ) -> dict[str, Any]:
        final_identity_path = campaign_evidence_dir(
            self.state_root, manifest.campaign_id
        ) / "control/final_candidate_identity.json"
        if not final_identity_path.is_file():
            raise ControlPlaneError("finalizing campaign has no bound candidate identity")
        recorded = json.loads(final_identity_path.read_text(encoding="utf-8"))
        if recorded != candidate_identity:
            raise ControlPlaneError("finalizing campaign candidate identity drifted")
        state = self.store.summary(manifest.campaign_id)["state"]
        if state == LifecycleState.CLOSED.value:
            sealed = self._verified_existing_seal(manifest.campaign_id)
            return {
                "status": "closed",
                "campaign_id": manifest.campaign_id,
                "summary": self.store.summary(manifest.campaign_id),
                "sealed": sealed,
            }
        if state != LifecycleState.FINALIZING.value:
            raise ControlPlaneError("campaign is not ready for finalization")
        if self._seal_exists(manifest.campaign_id):
            # Publication is the durable recovery point.  A crash after it but
            # before the terminal state transition resumes here and verifies
            # the exact already-published bytes before exposing CLOSED.
            sealed = self._verified_existing_seal(manifest.campaign_id)
        else:
            write_summary(self.state_root, self.store, manifest.campaign_id)
            sealed = self.seal_evidence(manifest.campaign_id)
            self._verified_existing_seal(manifest.campaign_id)
        self.store.set_state(manifest.campaign_id, LifecycleState.CLOSED)
        return {
            "status": "closed",
            "campaign_id": manifest.campaign_id,
            "summary": self.store.summary(manifest.campaign_id),
            "sealed": sealed,
        }

    def _seal_exists(self, campaign_id: str) -> bool:
        root = campaign_evidence_dir(self.state_root, campaign_id)
        output = self.state_root / "sealed" / f"{root.name}.seal"
        return all(
            path.is_file()
            for path in (
                output / f"{root.name}.manifest.json",
                output / f"{root.name}.tar.gz",
                output / f"{root.name}.tar.gz.sha256",
            )
        )

    def _existing_seal(self, campaign_id: str) -> dict[str, str]:
        root = campaign_evidence_dir(self.state_root, campaign_id)
        output = self.state_root / "sealed" / f"{root.name}.seal"
        manifest = output / f"{root.name}.manifest.json"
        archive = output / f"{root.name}.tar.gz"
        checksum = output / f"{root.name}.tar.gz.sha256"
        anchor = (
            self.state_root.parent
            / f".{self.state_root.name}-evidence-trust-anchors"
            / f"{root.name}.anchor.json"
        )
        return verify_seal(manifest, archive, checksum, anchor)

    def _verified_existing_seal(self, campaign_id: str) -> dict[str, str]:
        sealed = self._existing_seal(campaign_id)
        root = campaign_evidence_dir(self.state_root, campaign_id)
        published_manifest = json.loads(Path(sealed["manifest"]).read_text(encoding="utf-8"))
        if published_manifest != snapshot_manifest(root):
            raise ControlPlaneError("published seal does not match current campaign evidence")
        return sealed

    def _resolve_baseline(self, manifest: CampaignManifest) -> str:
        if manifest.baseline == "HEAD":
            return git_head(self.project_root)
        if manifest.baseline == "BASELINE_COMMIT":
            return DEFAULT_BASELINE
        return manifest.baseline

    def _reconcile_runtime_noise(self, manifest: CampaignManifest) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for item in manifest.validation_controls.deterministic_runtime_noise:
            self.executor.guard.validate_runtime_noise(
                item.path, tuple(manifest.scope.get("allowed_write_paths", []))
            )
            removed = self.executor.filesystem.remove(item.path, item.kind)
            existed = removed
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
        payload: dict[str, Any] = {
            "phase": "reconcile",
            "failure_class": None,
            "runtime_noise": entries,
        }
        write_control_envelope(self.state_root, manifest.campaign_id, "reconcile", payload)
        return payload

    def _resume_without_runtime_noise_reconciliation(
        self, manifest: CampaignManifest
    ) -> dict[str, Any]:
        """Preserve outputs owned by completed activities during campaign resume."""
        payload: dict[str, Any] = {
            "phase": "reconcile",
            "failure_class": None,
            "runtime_noise": [],
            "skipped": "completed_activity_resume",
        }
        write_control_envelope(
            self.state_root, manifest.campaign_id, "reconcile_resume", payload
        )
        return payload

    def _authorize_before_mutation(self, manifest: CampaignManifest) -> dict[str, Any] | None:
        """Authorize every effect before state, evidence, hydration, or cleanup changes."""
        for activity in manifest.activities:
            decision = self.policy.evaluate(activity.action, activity.risk)
            if decision.outcome == "pause":
                return {
                    "status": "human_gate",
                    "campaign_id": manifest.campaign_id,
                    "decision": decision.to_record(),
                }
            if decision.outcome != "allow":
                return {
                    "status": "failed",
                    "campaign_id": manifest.campaign_id,
                    "failure_class": FailureClass.POLICY_DENIAL.value,
                }
            self.executor.guard.resolve(activity)
        scope = tuple(manifest.scope.get("allowed_write_paths", []))
        for item in manifest.validation_controls.deterministic_runtime_noise:
            self.executor.guard.validate_runtime_noise(item.path, scope)
        return None

    def _hydrate_prerequisites(self, manifest: CampaignManifest) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        missing: list[str] = []
        for item in manifest.validation_controls.trusted_prerequisites:
            kind_before = self.executor.filesystem.kind(item.path)
            existed_before = kind_before is not None
            if not existed_before and item.hydrate and item.kind == "directory":
                self.executor.filesystem.mkdir(item.path)
            kind_after = self.executor.filesystem.kind(item.path)
            exists_after = kind_after is not None
            kind_matches = kind_after == item.kind
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
        candidate_identity: dict[str, str],
    ) -> dict[str, Any]:
        if hasattr(self.executor, "observe_at"):
            with tempfile.TemporaryDirectory(prefix="upi_baseline_subject_") as temporary:
                baseline_root = Path(temporary) / "repository"
                self._materialize_baseline(baseline, baseline_root)
                baseline_result = self.executor.observe_at(
                    activity, "baseline", baseline, baseline_root
                ).to_record()
        else:
            # Controlled test executors model outcomes directly and never execute code.
            baseline_result = self.executor.observe(activity, "baseline", baseline).to_record()
        before = git_worktree_identity(self.project_root)
        if before != candidate_identity:
            raise ControlPlaneError("candidate identity drifted before observation")
        candidate_reference = f"WORKTREE:{before['head']}:{before['tree_sha256']}"
        if isinstance(self.executor, CapabilityExecutor):
            candidate_result = self.executor.observe(
                activity,
                "candidate",
                candidate_reference,
                expected_identity=before,
            ).to_record()
        else:
            candidate_result = self.executor.observe(
                activity, "candidate", candidate_reference
            ).to_record()
        if git_worktree_identity(self.project_root) != before:
            raise ControlPlaneError("candidate identity drifted during observation")
        failure_class = self._classify_observation(baseline_result, candidate_result)
        payload = {
            "phase": "classify",
            "activity": _activity_record(activity),
            "baseline": baseline,
            "baseline_result": baseline_result,
            "candidate_result": candidate_result,
            "candidate_identity": before,
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

    def _materialize_baseline(self, baseline: str, destination: Path) -> None:
        completed = subprocess.run(
            ["git", "-C", str(self.project_root), "archive", "--format=tar", baseline],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise ControlPlaneError("baseline commit could not be materialized")
        destination.mkdir(mode=0o700)
        try:
            with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
                for member in archive.getmembers():
                    path = Path(member.name)
                    if path.is_absolute() or ".." in path.parts or not (
                        member.isdir() or member.isfile()
                    ):
                        raise ControlPlaneError("baseline archive contains an unsafe member")
                    target = destination / path
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ControlPlaneError("baseline archive member is unreadable")
                    target.write_bytes(stream.read())
        except tarfile.TarError as exc:
            raise ControlPlaneError("baseline archive is invalid") from exc

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
