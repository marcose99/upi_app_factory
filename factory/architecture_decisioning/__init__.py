"""Deterministic governed architecture-decision kernel public API."""

from .canonical import canonical_sha256
from .constraints import evaluate_constraints
from .driver_compiler import compile_driver_ir
from .durability import (
    build_evolution_contract,
    evaluate_durability,
    verify_evolution_contract,
)
from .engine import decide_architecture
from .evidence import load_architecture_contract
from .freeze import freeze_architecture, verify_architecture_freeze
from .models import ArchitectureDecisionError, ArchitectureHumanGate
from .registry import generate_candidates
from .risk import classify_authority
from .scoring import score_candidates
from .sensitivity import run_sensitivity_analysis
from .adjudication import adjudicate_architecture_reviews
from .confidence import calculate_architecture_confidence
from .review_models import ArchitectureReviewError, ArchitectureReviewIncomplete
from .review_packet import (
    build_architecture_review_packet,
    build_review_requests,
    freeze_review_set,
)
from .review_supervisor import ArchitectureReviewSupervisor
from .review_validation import load_architecture_review_contract, validate_review_report
from .reviewed_freeze import (
    build_reviewed_architecture_package,
    freeze_reviewed_architecture,
    verify_reviewed_architecture_freeze,
    verify_reviewed_architecture_package,
)
from .prototype_resolution import (
    HUMAN_RESOLUTION_STATUS,
    resolve_prototype_required_adjudication,
    verify_human_resolved_adjudication,
)
from .dossier import (
    ARCHITECTURE_CHANGING_NFR_DRIVER_IDS,
    BOUNDED_CLAIM_STATUS,
    SUFFICIENT_CLAIM_STATUS,
    build_architecture_decision_dossier,
    evaluate_nfr_sufficiency,
    render_architecture_decision_dossier_markdown,
    verify_architecture_decision_dossier,
)

__all__ = [
    "ArchitectureDecisionError", "ArchitectureHumanGate", "canonical_sha256",
    "classify_authority", "compile_driver_ir", "decide_architecture",
    "evaluate_constraints", "freeze_architecture", "generate_candidates",
    "load_architecture_contract", "run_sensitivity_analysis", "score_candidates",
    "verify_architecture_freeze", "evaluate_durability", "build_evolution_contract",
    "verify_evolution_contract",
    "ArchitectureReviewError", "ArchitectureReviewIncomplete",
    "ArchitectureReviewSupervisor", "load_architecture_review_contract",
    "build_architecture_review_packet", "build_review_requests",
    "validate_review_report", "freeze_review_set",
    "calculate_architecture_confidence", "adjudicate_architecture_reviews",
    "freeze_reviewed_architecture", "verify_reviewed_architecture_freeze",
    "build_reviewed_architecture_package", "verify_reviewed_architecture_package",
    "HUMAN_RESOLUTION_STATUS", "resolve_prototype_required_adjudication",
    "verify_human_resolved_adjudication",
    "ARCHITECTURE_CHANGING_NFR_DRIVER_IDS", "BOUNDED_CLAIM_STATUS",
    "SUFFICIENT_CLAIM_STATUS", "evaluate_nfr_sufficiency",
    "build_architecture_decision_dossier", "verify_architecture_decision_dossier",
    "render_architecture_decision_dossier_markdown",
]
