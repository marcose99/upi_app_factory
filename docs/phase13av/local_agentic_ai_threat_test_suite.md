# Phase 13AV — Local Agentic AI Threat-Test Suite

## Purpose

Phase 13AV turns agentic-AI and LLM risks into deterministic local threat tests.

The factory now creates local attack cases for prompt injection, insecure output handling, sensitive-data exposure, model denial of service, supply-chain compromise, RAG poisoning, tool abuse, excessive agency, overreliance, and malicious requirement packages.

## Safety boundary

Phase 13AV does not delete the real generated application.

Phase 13AV does not overwrite the real generated application.

Phase 13AV does not call live providers.

Phase 13AV does not call external systems.

Phase 13AV does not apply factory self-modifications.

Phase 13AV does not merge, tag, or release automatically.

## Threat-test families

```text
PROMPT_INJECTION
INSECURE_OUTPUT_HANDLING
SENSITIVE_INFORMATION_DISCLOSURE
MODEL_DENIAL_OF_SERVICE
SUPPLY_CHAIN_COMPROMISE
RAG_POISONING
TOOL_ABUSE
EXCESSIVE_AGENCY
OVERRELIANCE
UNTRUSTED_REQUIREMENT_PACKAGE
```

## Required controls

```text
block_instruction_override
sanitize_untrusted_output
redact_sensitive_data
enforce_size_limits
verify_artifact_provenance
isolate_untrusted_context
enforce_tool_allowlist
require_human_approval
require_evidence_grounding
reject_malicious_requirement
```

## Governance improvement introduced

Phase 13AU proved bounded low-risk repair in sandbox mode. Phase 13AV adds deterministic agentic-AI threat testing so the factory can locally certify that its agent controls resist common LLM, tool, RAG, and requirement-package attacks.
