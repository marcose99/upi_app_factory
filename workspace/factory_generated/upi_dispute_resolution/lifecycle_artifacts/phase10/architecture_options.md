# Phase 10 Architecture Options — upi_dispute_resolution

## Decision problem

Select a planning architecture that generates lifecycle artifacts before code
generation while preserving governance, traceability, mocked boundaries,
quality dimensions, regulatory-alignment themes, and economics.

## Option A — Single deterministic planner

### Summary

A single Python module generates all Phase 10 artifacts from deterministic
templates.

### Pros

- Lowest implementation complexity.
- Lowest runtime cost.
- Easy for beginners to debug.
- Strong reproducibility.
- Good for a capstone demonstration.

### Cons

- Limited flexibility for future complex requirement intake.
- Harder to scale to many domains.
- Less realistic for enterprise multi-agent planning.

### Economics

- Low build cost and low run cost.
- Low review cost for simple scenarios.
- Higher future change cost if requirements become diverse.

### Governance fit

Good for deterministic-first safety, but weaker for role separation.

## Option B — Event-driven multi-service planning pipeline

### Summary

Requirements, domain analysis, architecture, design, WBS, and traceability are
separate services connected by a message bus.

### Pros

- Closest to large enterprise topology.
- Strong separation of responsibilities.
- Easier to scale individual services.
- Natural fit for asynchronous review and event sourcing.

### Cons

- High implementation cost at this project stage.
- More infrastructure and operational complexity.
- Higher debugging burden.
- Higher cost for a laptop-based mock factory.

### Economics

- Higher build cost, run cost, and operational cost.
- Useful later when throughput, team ownership, and deployment isolation matter.
- Not cost-effective for the current deterministic capstone phase.

### Governance fit

Strong if implemented correctly, but risk of over-engineering now.

## Option C — Governed modular monolith with replaceable ports/adapters

### Summary

A deterministic planning core generates lifecycle artifacts. Each planner
capability is separated by module contracts and can later be replaced by
agents, workflow steps, policy engines, external stores, or human review.

### Pros

- Preserves deterministic-first behavior.
- Beginner-readable and debug-friendly.
- Supports future agent replacement without heavy infrastructure now.
- Keeps governance, validation, traceability, and economics visible.
- Suitable for repeated regeneration demos.

### Cons

- Not a full distributed enterprise platform yet.
- Requires discipline to keep ports/adapters clean.
- Some agent behavior remains synthetic until later phases.

### Economics

- Balanced build cost and future flexibility.
- Lower run cost than event-driven microservices.
- Lower change cost than a single hard-coded planner.
- Reduces vendor lock-in through replaceable interfaces.
- Keeps human review focused on high-risk ambiguity instead of mechanical work.

### Governance fit

Best fit for current project direction: mock-safe, deterministic-first,
evidence-driven, modular, and near-certifiable in posture without making
certification claims.

## Recommended selection

Select Option C.

Reason: Option C offers the best balance across safety, economics, governance,
debuggability, modularity, and future scalability. It supports the factory
vision without introducing avoidable infrastructure cost or false compliance
claims.

## Required honesty labels

- MISSING_OFFICIAL_SOURCE
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- MOCK_BOUNDARY
- SYNTHETIC_DATA
