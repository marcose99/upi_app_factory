# Phase 13S - Agent-Owned Application Capability Generation

Phase 13S is the first phase where the governed agentic runner owns generation
of a small real application capability.

## Generated capability

The generated capability validates UPI dispute evidence upload metadata.
It includes:

- Pydantic request and response contracts;
- deterministic local validation logic;
- generated behavioral tests;
- requirement-to-code-to-test traceability;
- lifecycle evidence artifacts.

## Governance boundary

The generated application capability is local and runnable. External banks,
NPCI-style systems, RBI-style systems, PSPs, UPI rails, document stores, malware
scanners, upstream applications, and downstream applications remain mock or
simulated boundaries only.

## Agent ownership

The Phase 13S runner uses LangGraph `StateGraph` agents for requirement package
normalization, design, code generation, test generation, documentation,
validation, bounded repair routing, and evidence persistence.
