from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterable, Mapping

from factory.application_engineering.deep_composer import DeepApplicationComposer
from factory.application_engineering.requirements_compiler import compile_requirements


PHASE70_SCHEMA_VERSION = "phase70-multi-domain-application-engineering.v1"
PROFILE_VERSION = "capability-profile/v1"
PRODUCT_NAME = "UPI App Factory"
REPOSITORY_ID = "upi_app_factory"
CERTIFICATION_POSTURE = "certification-ready-not-certified"
PROFILE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{2,96}$")
FORBIDDEN_RUNTIME_PHRASES = (
    "real payment calls enabled",
    "production ready",
    "officially certified",
    "certified by npci",
    "certified by rbi",
    "live bank api",
    "live psp api",
    "live card network",
)

REQUIRED_PROFILE_IDS = (
    "upi_failed_debit_no_credit",
    "upi_reversal_refund_tracking",
    "upi_duplicate_debit",
    "merchant_qr_acquirer_dispute",
    "fraud_mule_account_triage",
    "card_authorization_chargeback",
)

OBLIGATION_CATEGORIES = (
    "unit",
    "integration",
    "contract",
    "negative",
    "resilience",
    "security",
    "performance_smoke",
    "replay_audit",
)


class Phase70Error(ValueError):
    """Raised when the Phase 70 multi-domain contract fails closed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_child(root: Path, *parts: str) -> Path:
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise Phase70Error(f"path escapes runtime root: {candidate}") from exc
    return candidate


@dataclass(frozen=True)
class ValueObject:
    name: str
    validation: str
    redaction: str = "no raw PII in logs or evidence"


@dataclass(frozen=True)
class Transition:
    source: str
    target: str
    guard: str
    event: str


@dataclass(frozen=True)
class BoundaryPort:
    name: str
    direction: str
    mock_adapter: str
    live_calls: str = "disabled"


@dataclass(frozen=True)
class CapabilityProfile:
    profile_id: str
    title: str
    requirement_ids: tuple[str, ...]
    domain_states: tuple[str, ...]
    transitions: tuple[Transition, ...]
    value_objects: tuple[ValueObject, ...]
    policies: tuple[str, ...]
    events: tuple[str, ...]
    commands: tuple[str, ...]
    queries: tuple[str, ...]
    ports: tuple[BoundaryPort, ...]
    services: tuple[str, ...]
    mock_cases: tuple[str, ...]
    residual_risks: tuple[str, ...]
    depth_score: int
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["profile_version"] = PROFILE_VERSION
        payload["product_name"] = PRODUCT_NAME
        payload["repository_id"] = REPOSITORY_ID
        payload["certification_posture"] = CERTIFICATION_POSTURE
        payload["real_payment_calls"] = "disabled"
        payload["runtime_llm_calls_default"] = 0
        payload["fictional_data_only"] = True
        payload["expectations"] = {
            "idempotency": "command idempotency key returns the original outcome",
            "concurrency": "optimistic aggregate version rejects stale writes",
            "replay": "event replay rebuilds the same projection checksum",
            "audit_chain": "audit records carry previous_hash and record_hash",
            "outbox": "domain events are written atomically before mock publication",
            "authorization": "fictional local role and object-scope checks are required",
            "pii_redaction": "account, card, phone, and VPA-like values are masked",
            "safe_input_validation": "strict identifiers, amount bounds, and enum values fail closed",
        }
        payload["test_obligations"] = [
            {
                "category": category,
                "obligation_id": f"{self.profile_id}:{category}",
                "method": "deterministic local test or evidence assertion",
            }
            for category in OBLIGATION_CATEGORIES
        ]
        payload["stable_profile_sha256"] = sha256_json(
            {
                "profile_id": self.profile_id,
                "requirement_ids": self.requirement_ids,
                "domain_states": self.domain_states,
                "transitions": [asdict(item) for item in self.transitions],
                "commands": self.commands,
                "queries": self.queries,
                "ports": [asdict(item) for item in self.ports],
            }
        )
        return payload

    def validate(self) -> None:
        if not PROFILE_ID_PATTERN.fullmatch(self.profile_id):
            raise Phase70Error(f"invalid profile id: {self.profile_id}")
        if self.profile_id not in REQUIRED_PROFILE_IDS:
            raise Phase70Error(f"unexpected profile id: {self.profile_id}")
        if len(self.requirement_ids) < 4 or any(not SAFE_IDENTIFIER_PATTERN.fullmatch(item) for item in self.requirement_ids):
            raise Phase70Error(f"{self.profile_id} has insufficient stable requirement lineage")
        if len(self.domain_states) < 5 or self.domain_states[0] != "received":
            raise Phase70Error(f"{self.profile_id} must expose a received-led domain lifecycle")
        state_set = set(self.domain_states)
        if not all(item.source in state_set and item.target in state_set for item in self.transitions):
            raise Phase70Error(f"{self.profile_id} transition references unknown state")
        if len(self.value_objects) < 4 or len(self.policies) < 4 or len(self.events) < 4:
            raise Phase70Error(f"{self.profile_id} domain model is too shallow")
        if len(self.commands) < 4 or len(self.queries) < 3 or len(self.ports) < 3 or len(self.services) < 3:
            raise Phase70Error(f"{self.profile_id} application surface is too shallow")
        if {port.live_calls for port in self.ports} != {"disabled"}:
            raise Phase70Error(f"{self.profile_id} contains a live boundary")
        if self.depth_score < 82:
            raise Phase70Error(f"{self.profile_id} depth score is below Phase 70 threshold")
        if len(self.residual_risks) < 2:
            raise Phase70Error(f"{self.profile_id} must report residual risks")
        serialized = canonical_json(self.as_dict()).lower()
        for phrase in FORBIDDEN_RUNTIME_PHRASES:
            if phrase in serialized:
                raise Phase70Error(f"{self.profile_id} contains forbidden phrase: {phrase}")


def _base_states() -> tuple[str, ...]:
    return ("received", "validated", "evidence_pending", "investigation", "decisioned", "remediated", "closed", "rejected")


def _transitions(decision_event: str) -> tuple[Transition, ...]:
    return (
        Transition("received", "validated", "required identifiers and fictional principal scope are valid", "case_validated"),
        Transition("received", "rejected", "safe input validation fails closed", "case_rejected"),
        Transition("validated", "evidence_pending", "mock rail/acquirer evidence is not yet complete", "evidence_requested"),
        Transition("evidence_pending", "investigation", "all required mock evidence references are present", "investigation_started"),
        Transition("investigation", "decisioned", "policy score and guard outcomes are complete", decision_event),
        Transition("decisioned", "remediated", "mock remediation instruction is recorded in outbox", "remediation_recorded"),
        Transition("remediated", "closed", "audit chain verifies and customer-facing summary is redacted", "case_closed"),
        Transition("rejected", "closed", "rejection reason is redacted and immutable", "case_closed"),
    )


def _common_values(*extra: ValueObject) -> tuple[ValueObject, ...]:
    return (
        ValueObject("FictionalCaseId", "prefix plus checksum-stable suffix"),
        ValueObject("FictionalTransactionReference", "rail-specific reference pattern without real account data"),
        ValueObject("Money", "positive minor-unit amount and ISO-like currency code"),
        ValueObject("RedactedPartyHandle", "masked account, card, phone, and VPA-like tokens"),
        *extra,
    )


def build_phase70_profiles() -> tuple[CapabilityProfile, ...]:
    return (
        CapabilityProfile(
            "upi_failed_debit_no_credit",
            "UPI failed debit/no credit",
            ("P70-FDNC-REQ-001", "P70-FDNC-DOM-002", "P70-FDNC-APP-003", "P70-FDNC-EVD-004"),
            _base_states(),
            _transitions("failed_debit_decisioned"),
            _common_values(ValueObject("BeneficiaryCreditStatus", "mock CBS credit status enum")),
            ("failed debit SLA policy", "customer communication redaction policy", "mock switch lookup policy", "refund eligibility policy"),
            ("FailedDebitCaseOpened", "MockSwitchStatusRequested", "CreditNotFound", "RefundInstructionQueued"),
            ("OpenFailedDebitCase", "AttachMockSwitchEvidence", "AssessFailedDebit", "RecordMockRefundInstruction"),
            ("GetFailedDebitCase", "ListFailedDebitWorkQueue", "GetFailedDebitAuditTrail"),
            (
                BoundaryPort("MockUpiSwitchPort", "outbound", "FictionalUpiSwitchAdapter"),
                BoundaryPort("MockCoreBankingPort", "outbound", "FictionalCoreBankingAdapter"),
                BoundaryPort("RedactedNotificationPort", "outbound", "LocalNotificationRecorder"),
            ),
            ("FailedDebitCommandService", "FailedDebitQueryService", "FailedDebitReplayService"),
            ("FDNC-CASE-001", "FDNC-CASE-002"),
            ("Mock beneficiary credit evidence is representative only", "Offline SLA clock uses deterministic fixture time"),
            90,
            ("requirements_traceability.json", "profile_contract.json", "reference_app_manifest.json"),
        ),
        CapabilityProfile(
            "upi_reversal_refund_tracking",
            "UPI reversal or refund tracking",
            ("P70-RR-REQ-001", "P70-RR-DOM-002", "P70-RR-APP-003", "P70-RR-EVD-004"),
            _base_states(),
            _transitions("reversal_tracking_decisioned"),
            _common_values(ValueObject("RefundRailReference", "fictional refund reference with stable checksum")),
            ("refund status normalization policy", "aging bucket policy", "duplicate reversal suppression policy", "customer-safe status policy"),
            ("RefundTrackingOpened", "MockRefundStatusObserved", "RefundAgingBreached", "RefundTrackingClosed"),
            ("OpenRefundTrackingCase", "PollMockRefundStatus", "RecordRefundStatus", "CloseRefundTrackingCase"),
            ("GetRefundTrackingCase", "ListRefundExceptions", "GetRefundReplayProjection"),
            (
                BoundaryPort("MockRefundRailPort", "outbound", "FictionalRefundStatusAdapter"),
                BoundaryPort("MockLedgerPort", "outbound", "FictionalLedgerAdapter"),
                BoundaryPort("OutboxPublisherPort", "outbound", "LocalOutboxRecorder"),
            ),
            ("RefundTrackingCommandService", "RefundTrackingQueryService", "RefundReplayService"),
            ("RR-CASE-001", "RR-CASE-002"),
            ("External refund rail timestamps are fixture-controlled", "No live refund confirmation is asserted"),
            88,
            ("requirements_traceability.json", "refund_status_contract.json", "audit_replay_report.json"),
        ),
        CapabilityProfile(
            "upi_duplicate_debit",
            "UPI duplicate debit",
            ("P70-DD-REQ-001", "P70-DD-DOM-002", "P70-DD-APP-003", "P70-DD-EVD-004"),
            _base_states(),
            _transitions("duplicate_debit_decisioned"),
            _common_values(ValueObject("DuplicateClusterKey", "same payer, payee, amount, window, and mock rail fingerprint")),
            ("duplicate clustering policy", "stale write rejection policy", "idempotent intake policy", "redressed duplicate policy"),
            ("DuplicateDebitCaseOpened", "DuplicateCandidateMatched", "DuplicateDebitConfirmed", "DuplicateRemediationQueued"),
            ("OpenDuplicateDebitCase", "MatchDuplicateCandidate", "ConfirmDuplicateDebit", "QueueDuplicateDebitRemediation"),
            ("GetDuplicateDebitCase", "ListDuplicateClusters", "GetDuplicateAuditTrail"),
            (
                BoundaryPort("MockTransactionLedgerPort", "outbound", "FictionalTransactionLedgerAdapter"),
                BoundaryPort("MockDuplicateMatcherPort", "outbound", "DeterministicDuplicateMatcher"),
                BoundaryPort("AuditChainPort", "outbound", "LocalHashChainStore"),
            ),
            ("DuplicateDebitCommandService", "DuplicateDebitQueryService", "DuplicateReplayService"),
            ("DD-CASE-001", "DD-CASE-002"),
            ("Duplicate windows are fixture-tuned", "Cluster matching does not infer real customer behavior"),
            89,
            ("cluster_policy_evidence.json", "requirements_traceability.json", "replay_projection.json"),
        ),
        CapabilityProfile(
            "merchant_qr_acquirer_dispute",
            "Merchant QR/acquirer dispute",
            ("P70-MQA-REQ-001", "P70-MQA-DOM-002", "P70-MQA-APP-003", "P70-MQA-EVD-004"),
            _base_states(),
            _transitions("merchant_qr_decisioned"),
            _common_values(ValueObject("MerchantQrFingerprint", "fictional merchant/acquirer/terminal tuple")),
            ("merchant consent evidence policy", "QR payload validation policy", "acquirer evidence deadline policy", "settlement mock reconciliation policy"),
            ("MerchantQrCaseOpened", "AcquirerEvidenceRequested", "QrPayloadMismatchFound", "AcquirerDecisionRecorded"),
            ("OpenMerchantQrDispute", "RequestAcquirerEvidence", "ValidateQrPayload", "RecordAcquirerDecision"),
            ("GetMerchantQrCase", "ListAcquirerDisputes", "GetMerchantQrAuditTrail"),
            (
                BoundaryPort("MockAcquirerPort", "outbound", "FictionalAcquirerEvidenceAdapter"),
                BoundaryPort("MockMerchantRegistryPort", "outbound", "FictionalMerchantRegistry"),
                BoundaryPort("QrPayloadValidatorPort", "outbound", "DeterministicQrValidator"),
            ),
            ("MerchantQrCommandService", "MerchantQrQueryService", "MerchantQrReplayService"),
            ("MQA-CASE-001", "MQA-CASE-002"),
            ("Acquirer evidence is synthetic", "QR parsing covers representative local payloads only"),
            87,
            ("acquirer_contract.json", "requirements_traceability.json", "qr_validation_report.json"),
        ),
        CapabilityProfile(
            "fraud_mule_account_triage",
            "Fraud or mule-account triage",
            ("P70-FMT-REQ-001", "P70-FMT-DOM-002", "P70-FMT-APP-003", "P70-FMT-EVD-004"),
            _base_states(),
            _transitions("fraud_triage_decisioned"),
            _common_values(ValueObject("TriageSignalSet", "bounded fictional risk signals with source lineage")),
            ("least-data triage policy", "adverse action wording policy", "manual review escalation policy", "mule-link mock graph policy"),
            ("FraudTriageOpened", "RiskSignalsCollected", "ManualReviewRequired", "TriageOutcomeRecorded"),
            ("OpenFraudTriageCase", "AttachRiskSignals", "EscalateManualReview", "RecordTriageOutcome"),
            ("GetFraudTriageCase", "ListTriageQueue", "GetTriageEvidenceLedger"),
            (
                BoundaryPort("MockRiskSignalPort", "outbound", "FictionalRiskSignalAdapter"),
                BoundaryPort("MockMuleGraphPort", "outbound", "FictionalGraphAdapter"),
                BoundaryPort("CaseAccessPolicyPort", "outbound", "LocalRolePolicyAdapter"),
            ),
            ("FraudTriageCommandService", "FraudTriageQueryService", "FraudReplayService"),
            ("FMT-CASE-001", "FMT-CASE-002"),
            ("No automated law-enforcement reporting is claimed", "Risk scoring is deterministic and fictional"),
            91,
            ("risk_signal_lineage.json", "requirements_traceability.json", "redaction_matrix.json"),
        ),
        CapabilityProfile(
            "card_authorization_chargeback",
            "Card authorization exception or chargeback",
            ("P70-CAC-REQ-001", "P70-CAC-DOM-002", "P70-CAC-APP-003", "P70-CAC-EVD-004"),
            _base_states(),
            _transitions("card_exception_decisioned"),
            _common_values(ValueObject("MaskedCardReference", "BIN and last4 test tokens only; PAN forbidden")),
            ("auth exception classification policy", "chargeback representment evidence policy", "masked card data policy", "mock network deadline policy"),
            ("CardExceptionOpened", "AuthTraceMatched", "ChargebackEvidenceCompiled", "RepresentmentDecisionRecorded"),
            ("OpenCardExceptionCase", "MatchMockAuthTrace", "CompileChargebackEvidence", "RecordRepresentmentDecision"),
            ("GetCardExceptionCase", "ListChargebackQueue", "GetCardAuditTrail"),
            (
                BoundaryPort("MockCardNetworkPort", "outbound", "FictionalCardNetworkAdapter"),
                BoundaryPort("MockIssuerLedgerPort", "outbound", "FictionalIssuerLedger"),
                BoundaryPort("EvidenceVaultPort", "outbound", "LocalEvidenceVault"),
            ),
            ("CardExceptionCommandService", "CardExceptionQueryService", "CardReplayService"),
            ("CAC-CASE-001", "CAC-CASE-002"),
            ("Network reason codes are illustrative", "No PCI certification or live card processing is asserted"),
            89,
            ("card_exception_contract.json", "requirements_traceability.json", "safe_pan_scan.json"),
        ),
    )


def _reference_app_files(profile: CapabilityProfile) -> dict[str, str]:
    profile_payload = profile.as_dict()
    transition_rows = "\n".join(
        f"    ({item.source!r}, {item.target!r}): {item.guard!r}," for item in profile.transitions
    )
    event_rows = "\n".join(f"    {event!r}," for event in profile.events)
    command_rows = "\n".join(f"    {command!r}," for command in profile.commands)
    query_rows = "\n".join(f"    {query!r}," for query in profile.queries)
    port_rows = "\n".join(f"    {asdict(port)!r}," for port in profile.ports)
    return {
        "app/__init__.py": "",
        f"app/{profile.profile_id}/__init__.py": f'"""Reference app for {profile.title}."""\n',
        f"app/{profile.profile_id}/domain/model.py": f"""from __future__ import annotations

DOMAIN_STATES = {profile.domain_states!r}
TRANSITION_GUARDS = {{
{transition_rows}
}}
DOMAIN_EVENTS = (
{event_rows}
)
VALUE_OBJECTS = {tuple(asdict(item) for item in profile.value_objects)!r}
POLICIES = {profile.policies!r}
""",
        f"app/{profile.profile_id}/application/contracts.py": f"""from __future__ import annotations

COMMANDS = (
{command_rows}
)
QUERIES = (
{query_rows}
)
PORTS = (
{port_rows}
)
SERVICES = {profile.services!r}
EXPECTATIONS = {profile_payload["expectations"]!r}
TEST_OBLIGATIONS = {profile_payload["test_obligations"]!r}
""",
        f"app/{profile.profile_id}/security/guards.py": """from __future__ import annotations

import re

SAFE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{2,96}$")


def validate_safe_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError("unsafe identifier")
    return value


def redact(value: str) -> str:
    value = re.sub(r"\\b\\d{12,19}\\b", "[masked-card]", value)
    value = re.sub(r"\\b\\d{9,18}\\b", "[masked-account]", value)
    return re.sub(r"[A-Za-z0-9._-]+@[A-Za-z0-9._-]+", "[masked-handle]", value)
""",
        f"app/{profile.profile_id}/infrastructure/mocks.py": f"""from __future__ import annotations

MOCK_ONLY = True
REAL_PAYMENT_CALLS = "disabled"
MOCK_CASES = {profile.mock_cases!r}
""",
        "tests/test_contract.py": f"""from app.{profile.profile_id}.application.contracts import COMMANDS, QUERIES, PORTS, TEST_OBLIGATIONS
from app.{profile.profile_id}.domain.model import DOMAIN_EVENTS, DOMAIN_STATES, TRANSITION_GUARDS


def test_profile_contract_depth():
    assert DOMAIN_STATES[0] == "received"
    assert len(TRANSITION_GUARDS) >= 8
    assert len(COMMANDS) >= 4
    assert len(QUERIES) >= 3
    assert all(port["live_calls"] == "disabled" for port in PORTS)
    assert len(TEST_OBLIGATIONS) == 8
    assert len(DOMAIN_EVENTS) >= 4
""",
        "evidence/profile_contract.json": json.dumps(profile_payload, indent=2, sort_keys=True) + "\n",
        "evidence/depth_score.json": json.dumps(
            {
                "profile_id": profile.profile_id,
                "depth_score": profile.depth_score,
                "threshold": 82,
                "residual_risks": list(profile.residual_risks),
                "certification_posture": CERTIFICATION_POSTURE,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }


def compose_reference_application(profile: CapabilityProfile, output_root: Path, project_root: Path) -> dict[str, Any]:
    profile.validate()
    root = safe_child(output_root, profile.profile_id)
    if root.exists():
        shutil.rmtree(root)
    for relative, content in _reference_app_files(profile).items():
        target = safe_child(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files.append({"path": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    manifest = {
        "schema_version": "phase70-reference-app-manifest.v1",
        "profile_id": profile.profile_id,
        "source": "factory.application_engineering.multi_domain_profiles",
        "composed_with": "Phase 56 deep composer contract shape plus profile-specific overlays",
        "reused_components": [
            "factory.application_engineering.requirements_compiler.compile_requirements",
            "factory.application_engineering.deep_composer.DeepApplicationComposer",
            "factory.application_engineering.verification_evidence evidence contract",
        ],
        "tracked_output": False,
        "runtime_root_inside": str(output_root.resolve()),
        "file_count": len(files),
        "file_manifest": files,
        "manifest_sha256": sha256_json({"profile_id": profile.profile_id, "files": files}),
    }
    write_json(root / "evidence" / "reference_app_manifest.json", manifest)
    return manifest


def load_governance_profiles(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Phase70Error("profile governance fixture must be a JSON object")
    return payload


def _validate_fixture_profiles(profiles: Iterable[CapabilityProfile], governance: Mapping[str, Any]) -> None:
    expected = {profile.profile_id: profile.as_dict()["stable_profile_sha256"] for profile in profiles}
    declared = governance.get("profiles")
    if not isinstance(declared, list):
        raise Phase70Error("governance profiles must be a list")
    declared_hashes = {item.get("profile_id"): item.get("stable_profile_sha256") for item in declared if isinstance(item, dict)}
    if declared_hashes != expected:
        raise Phase70Error("governance profile hashes do not match deterministic profile definitions")
    controls = set(governance.get("required_controls", []))
    required_controls = {
        "requirements_lineage",
        "domain_lifecycle_guards",
        "application_ports_services",
        "idempotency_concurrency_replay_audit_outbox",
        "authorization_pii_redaction_safe_validation",
        "mock_external_boundaries",
        "test_obligation_matrix",
        "depth_and_residual_risk_reporting",
    }
    if not required_controls.issubset(controls):
        raise Phase70Error("governance fixture is missing required controls")


def validate_phase70_portfolio(
    *,
    project_root: Path,
    requirements_root: Path,
    governance_path: Path,
    runtime_root: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    profiles = build_phase70_profiles()
    if tuple(profile.profile_id for profile in profiles) != REQUIRED_PROFILE_IDS:
        raise Phase70Error("profile portfolio does not match required Phase 70 contract")
    for profile in profiles:
        profile.validate()

    governance = load_governance_profiles(governance_path)
    _validate_fixture_profiles(profiles, governance)

    requirement_files = sorted(requirements_root.glob("*.md"))
    if len(requirement_files) < len(REQUIRED_PROFILE_IDS):
        raise Phase70Error("missing Phase 70 requirements fixtures")
    compiled = compile_requirements(requirement_files, project_root)
    blocking = [item for item in compiled["diagnostics"] if item["severity"] in {"critical", "error"}]
    if blocking:
        raise Phase70Error(f"requirements fixtures have blocking diagnostics: {blocking[0]['code']}")
    compiled_text = canonical_json(compiled)
    for profile in profiles:
        for requirement_id in profile.requirement_ids:
            if requirement_id not in compiled_text:
                raise Phase70Error(f"missing requirement lineage for {profile.profile_id}: {requirement_id}")

    runtime_root.mkdir(parents=True, exist_ok=True)
    ignored_tmp = project_root / "tmp"
    ignored_tmp.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase70_deep_composer_reuse_", dir=ignored_tmp) as scratch:
        golden_manifest = DeepApplicationComposer(project_root).compose(
            requirements_ir=compiled,
            output_root=Path(scratch),
            app_id="phase70_failed_debit_reference",
        )
    reference_manifests = [
        compose_reference_application(profile, safe_child(runtime_root, "reference_apps"), project_root)
        for profile in profiles
    ]

    profile_payloads = [profile.as_dict() for profile in profiles]
    obligation_counts = {
        category: sum(
            1
            for profile in profile_payloads
            for item in profile["test_obligations"]
            if item["category"] == category
        )
        for category in OBLIGATION_CATEGORIES
    }
    result = {
        "schema_version": PHASE70_SCHEMA_VERSION,
        "status": "PASS",
        "product_name": PRODUCT_NAME,
        "repository_id": REPOSITORY_ID,
        "certification_posture": CERTIFICATION_POSTURE,
        "official_certification_claimed": False,
        "production_readiness_claimed": False,
        "fictional_data_only": True,
        "real_payment_calls": "disabled",
        "runtime_llm_calls_default": 0,
        "profile_count": len(profiles),
        "profiles": profile_payloads,
        "requirements_ir_sha256": compiled["canonical_hash"],
        "requirements_traceability_rows": len(compiled["traceability"]),
        "obligation_counts": obligation_counts,
        "depth": {
            "minimum_score": min(profile.depth_score for profile in profiles),
            "average_score": round(sum(profile.depth_score for profile in profiles) / len(profiles), 2),
            "threshold": 82,
        },
        "residual_risks": {
            profile.profile_id: list(profile.residual_risks)
            for profile in profiles
        },
        "reference_app_manifests": reference_manifests,
        "phase56_reuse_manifest": {
            "app_id": golden_manifest["app_id"],
            "composer_profile": golden_manifest["composer_profile"],
            "profile_version": golden_manifest["profile_version"],
            "real_payment_calls": golden_manifest["real_payment_calls"],
            "llm_runtime_calls": golden_manifest["llm_runtime_calls"],
        },
    }
    result["portfolio_sha256"] = sha256_json({key: value for key, value in result.items() if key != "portfolio_sha256"})
    return result
