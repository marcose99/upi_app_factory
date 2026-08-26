"""Deterministic maintenance lifecycle, reconciliation, and lineage evidence.

All assertions enter through caller-owned authoritative fact IDs.  This module
classifies those facts and projects them; it does not infer facts from prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from factory.documentation import EvidenceGraph, canonical_sha256


class MaintenanceModelError(ValueError):
    pass


class ChangeType(str, Enum):
    ENHANCEMENT = "ENHANCEMENT"
    BUG_FIX = "BUG_FIX"
    EMERGENCY_HOTFIX = "EMERGENCY_HOTFIX"
    SECURITY_REMEDIATION = "SECURITY_REMEDIATION"
    REGULATORY_BUSINESS_CHANGE = "REGULATORY_BUSINESS_CHANGE"
    DEPENDENCY_PLATFORM_CONFIGURATION = "DEPENDENCY_PLATFORM_CONFIGURATION"
    SCHEMA_DATA_MIGRATION = "SCHEMA_DATA_MIGRATION"
    PERFORMANCE_OBSERVABILITY_RESILIENCE = "PERFORMANCE_OBSERVABILITY_RESILIENCE"
    ROLLBACK_REVERT = "ROLLBACK_REVERT"
    DATA_CORRECTION = "DATA_CORRECTION"
    DEPRECATION_EOL = "DEPRECATION_EOL"


class ChangeKind(str, Enum):
    DEFECT = "DEFECT"
    NEW_REQUIREMENT = "NEW_REQUIREMENT"


class RepairLocus(str, Enum):
    REQUIREMENT_BASELINE = "REQUIREMENT_BASELINE"
    FACTORY_SYSTEMIC_CAPABILITY = "FACTORY_SYSTEMIC_CAPABILITY"
    APPLICATION_EVOLUTION_SPEC = "APPLICATION_EVOLUTION_SPEC"
    CONFIGURATION_CONTRACT = "CONFIGURATION_CONTRACT"
    DEPENDENCY_CONTRACT = "DEPENDENCY_CONTRACT"
    DATA_OPERATION = "DATA_OPERATION"
    TEMPORARY_HOTFIX = "TEMPORARY_HOTFIX"


@dataclass(frozen=True)
class ChangeRecord:
    change_id: str
    application_id: str
    change_type: ChangeType
    kind: ChangeKind
    repair_locus: RepairLocus
    source_fact_ids: tuple[str, ...]
    affected_fact_ids: tuple[str, ...] = ()
    implementation_fact_ids: tuple[str, ...] = ()
    test_fact_ids: tuple[str, ...] = ()
    release_id: str | None = None
    direct_generated_source_change: bool = False
    reconciliation_fact_ids: tuple[str, ...] = ()
    systemic_capability_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("change_id", "application_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise MaintenanceModelError(f"{name} must be a stable identifier")
        if not self.source_fact_ids or any(not item for item in self.source_fact_ids):
            raise MaintenanceModelError("a change requires authoritative source_fact_ids")
        if len(set(self.source_fact_ids)) != len(self.source_fact_ids):
            raise MaintenanceModelError("source_fact_ids must be unique")
        if self.change_type is ChangeType.EMERGENCY_HOTFIX and self.repair_locus is not RepairLocus.TEMPORARY_HOTFIX:
            raise MaintenanceModelError("emergency hotfixes begin at TEMPORARY_HOTFIX")
        if self.repair_locus is RepairLocus.FACTORY_SYSTEMIC_CAPABILITY and not self.systemic_capability_id:
            raise MaintenanceModelError("systemic repairs require a Factory capability identity")

    @property
    def reconciliation_required(self) -> bool:
        return self.direct_generated_source_change or self.repair_locus is RepairLocus.TEMPORARY_HOTFIX

    @property
    def reconciliation_status(self) -> str:
        return "PROVEN" if self.reconciliation_required and self.reconciliation_fact_ids else (
            "PENDING_EXTERNAL_AUTHORITY" if self.reconciliation_required else "NOT_APPLICABLE"
        )

    def to_dict(self) -> dict[str, Any]:
        body = {
            "affected_fact_ids": sorted(set(self.affected_fact_ids)),
            "application_id": self.application_id,
            "change_id": self.change_id,
            "change_kind": self.kind.value,
            "change_type": self.change_type.value,
            "direct_generated_source_change": self.direct_generated_source_change,
            "implementation_fact_ids": sorted(set(self.implementation_fact_ids)),
            "reconciliation_fact_ids": sorted(set(self.reconciliation_fact_ids)),
            "reconciliation_required": self.reconciliation_required,
            "reconciliation_status": self.reconciliation_status,
            "release_id": self.release_id,
            "repair_locus": self.repair_locus.value,
            "source_fact_ids": sorted(self.source_fact_ids),
            "systemic_capability_id": self.systemic_capability_id,
            "test_fact_ids": sorted(set(self.test_fact_ids)),
        }
        return {**body, "record_digest": canonical_sha256(body)}


@dataclass
class MaintenanceLedger:
    application_id: str
    records: list[ChangeRecord] = field(default_factory=list)

    def add(self, record: ChangeRecord) -> None:
        if record.application_id != self.application_id:
            raise MaintenanceModelError("change belongs to another application")
        if any(item.change_id == record.change_id for item in self.records):
            raise MaintenanceModelError(f"duplicate change_id: {record.change_id}")
        self.records.append(record)

    def impact(self, change_id: str, graph: EvidenceGraph) -> tuple[str, ...]:
        record = next((item for item in self.records if item.change_id == change_id), None)
        if record is None:
            raise MaintenanceModelError(f"unknown change_id: {change_id}")
        traversed = graph.traverse(change_id) if change_id in graph.node_ids() else ()
        return tuple(sorted(set(record.affected_fact_ids).union(traversed)))

    def gates(self) -> dict[str, Mapping[str, Any]]:
        missing_impact = sorted(r.change_id for r in self.records if not r.affected_fact_ids)
        bad_locus = sorted(r.change_id for r in self.records if r.repair_locus is RepairLocus.TEMPORARY_HOTFIX and r.change_type is not ChangeType.EMERGENCY_HOTFIX)
        unreconciled = sorted(r.change_id for r in self.records if r.reconciliation_required and not r.reconciliation_fact_ids)
        missing_trace = sorted(r.change_id for r in self.records if not r.implementation_fact_ids or not r.test_fact_ids)
        missing_lineage = sorted(r.change_id for r in self.records if r.release_id is None)
        def gate(name: str, errors: Iterable[str]) -> Mapping[str, Any]:
            values = list(errors)
            return {"gate": name, "status": "PROVEN" if not values else "FAIL", "change_ids": values}
        return {
            "CHANGE_PROVENANCE_GATE": gate("CHANGE_PROVENANCE_GATE", (r.change_id for r in self.records if not r.source_fact_ids)),
            "CHANGE_IMPACT_COMPLETENESS_GATE": gate("CHANGE_IMPACT_COMPLETENESS_GATE", missing_impact),
            "REPAIR_LOCUS_GATE": gate("REPAIR_LOCUS_GATE", bad_locus),
            "HOTFIX_RECONCILIATION_GATE": gate("HOTFIX_RECONCILIATION_GATE", unreconciled),
            "GENERATED_SOURCE_DRIFT_GATE": gate("GENERATED_SOURCE_DRIFT_GATE", unreconciled),
            "MAINTENANCE_TRACEABILITY_GATE": gate("MAINTENANCE_TRACEABILITY_GATE", missing_trace),
            "RELEASE_LINEAGE_GATE": gate("RELEASE_LINEAGE_GATE", missing_lineage),
        }

    def documents(self) -> dict[str, dict[str, Any]]:
        rows = [r.to_dict() for r in sorted(self.records, key=lambda x: x.change_id)]
        sources = sorted({fact for r in self.records for fact in r.source_fact_ids})
        gates = self.gates()
        systemic = [{"change_id": r.change_id, "factory_capability_id": r.systemic_capability_id,
                     "affected_application_ids": [self.application_id], "requalification_status": "NOT_YET_MEASURED"}
                    for r in self.records if r.systemic_capability_id]
        releases = [{"change_id": r.change_id, "release_id": r.release_id,
                     "release_status": "PROVEN" if r.release_id else "NOT_RELEASED"} for r in self.records]
        bodies = {
            "application_evolution_spec": {"changes": rows},
            "change_ledger": {"changes": rows},
            "maintenance_status": {"gates": gates, "open_reconciliation_ids": gates["HOTFIX_RECONCILIATION_GATE"]["change_ids"]},
            "release_lineage": {"entries": releases},
            "requirements_to_release_maintenance": {"entries": releases},
            "factory_learning_ledger": {"entries": systemic},
        }
        result = {}
        for name, body in bodies.items():
            core = {"applicability_status": "PROVEN", "document_id": f"DOC-{self.application_id}-{name}",
                    "generated_at": "DETERMINISTIC_FROM_CHANGE_FACT_IDENTITIES", "schema_version": "upi_app_factory.application-maintenance.v1",
                    "source_fact_ids": sources, "subject_id": self.application_id, **body}
            result[name] = {**core, "document_digest": canonical_sha256(core)}
        return result
