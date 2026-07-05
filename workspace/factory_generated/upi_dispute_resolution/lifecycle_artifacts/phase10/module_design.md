# Phase 10 Module Design — upi_dispute_resolution

## Module map

| Module | Responsibility | Inputs | Outputs | Economics handled |
|---|---|---|---|---|
| Requirement Analyzer | Converts project intent into structured requirements | Project direction, prior governance | requirements_analysis.json | Cost drivers, source gaps |
| Domain Analyzer | Explains payment dispute domain and boundaries | Requirements | domain_analysis.md | Manual ops, dispute economics |
| Architecture Optioner | Produces multiple architecture options | Requirements, domain | architecture_options.md | Build/run/change cost |
| ADR Writer | Selects architecture with justification | Options | architecture_decision_record.md | Cost-risk tradeoff |
| Module Designer | Defines modules and contracts | ADR | module_design.md | Modularity and replacement cost |
| HLD Generator | Produces high-level design | ADR, module design | hld.md | Runtime and operational cost |
| LLD Generator | Produces low-level design | HLD | lld.md | Debugging and rework cost |
| WBS Planner | Orders manageable tasks | Requirements/design | work_breakdown_structure.json | Effort and sequencing |
| Traceability Builder | Connects requirement to design to task | All artifacts | traceability_matrix.json | Audit/review cost |
| Planning Validator | Fails closed on missing evidence | All artifacts | planning_validation_report.json | Cost of poor planning |
| Economics Assessor | Makes economics explicit without inventing numbers | Requirements/domain | Embedded sections | ROI/source discipline |
| Mock Boundary Guard | Blocks live external dependencies | External adapter intents | Validation failures | Safety and incident cost |

## Design principles

1. Deterministic-first: stable policy, validation, and traceability are
   handled with deterministic logic before any future agent expansion.
2. Mock-safe: all bank, PSP, NPCI, RBI, notification, ledger, and customer
   channels are mock adapters.
3. Evidence-driven: every planning decision must point to a requirement,
   design section, or source-gap label.
4. Beginner-readable: plain names, small functions, clear errors, and
   direct validation reports.
5. Modular replacement: future phases can replace deterministic modules
   with governed agents one by one.
6. Economics-aware: build/run/change/rework/review/incident costs are
   considered before implementation.
7. Honest posture: MISSING_OFFICIAL_SOURCE is better than a guessed rule.

## Ports and adapters

- RequirementInputPort
- OfficialSourceReferencePort
- ArchitectureOptionPort
- DesignArtifactPort
- TraceabilityPort
- ValidationReportPort
- MockParticipantAdapterPort
- EconomicsAssessmentPort

## Mock external adapters

- MockCustomerAppAdapter
- MockRemitterBankAdapter
- MockBeneficiaryBankAdapter
- MockPspAdapter
- MockNpciOdrAdapter
- MockLedgerAdapter
- MockReconciliationAdapter
- MockNotificationAdapter

Every adapter is a MOCK_BOUNDARY.
