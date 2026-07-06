# Phase 13M - LangGraph Agentic Runtime + Dispute Lifecycle Slice

Phase 13M upgrades the local-first factory from deterministic script sequencing
to a proper LangGraph agentic runtime while keeping the software footprint
lightweight.

## Lightweight does not mean non-agentic

The default runtime remains local-first and manageable, but the agent
orchestration must use a real agent framework. Phase 13M uses LangGraph
`StateGraph` for stateful multi-agent orchestration.

## Scope

The generated application expands from Phase 13L's dispute-intake slice into a
runnable dispute lifecycle slice:

1. create case;
2. validate evidence;
3. request simulated investigation;
4. process mock investigation response;
5. propose resolution;
6. finalize resolution;
7. preserve audit trail.

## Governance boundary

The primary generated UPI dispute lifecycle application is local and runnable.
External banks, rails, NPCI-style, RBI-style, upstream systems, and downstream
integrations remain simulated mock boundaries.

## Agent graph

The LangGraph graph contains:

- requirement intake agent;
- domain model agent;
- application slice agent;
- ecosystem mock agent;
- verification agent;
- conditional self-correction agent route;
- governance evidence agent.

The conditional self-correction route is part of the graph topology and is used
when validation fails.
