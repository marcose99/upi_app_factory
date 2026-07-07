# Phase 14V — Autonomous Quality-Gate Pipeline Hardening

Phase 14V hardens the governed autonomous continuation model so the factory can move quickly toward Phase 14Z without weakening quality.

The phase introduces a quality-gate pipeline that separates gates by mutation behavior, safety boundary, and rerun requirement:

1. **Read-only parallel gates** may run concurrently when they do not mutate tracked state.
2. **Audit-producing gates** must write explicit lifecycle evidence and that evidence must be committed before legacy drift-sensitive full regression.
3. **Full regression** must run from a clean committed tree.
4. **Cataloged low-risk repairs** may be proposed or applied only under policy and must rerun impacted gates.
5. **Human-gated boundaries** remain: merge, tag, push, release, promotion, live-provider calls, destructive operations, and official certification claims.

This phase also formalizes the lesson learned from Phase 14U: validators and targeted tests must avoid refreshing tracked lifecycle audit evidence during final non-mutating verification. Tests that need audit evidence should use temporary audit files.

The factory remains certification-ready-not-certified. It can produce evidence for certification review, but it cannot grant or claim official certification.
