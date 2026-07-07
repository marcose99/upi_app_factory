# Phase 13AW — Local Factory Operator Portal Foundation

## Purpose

Phase 13AW introduces the local Factory Operator Portal foundation.

The portal is intended for another person to use the factory from a local browser without manually inspecting every script, JSON evidence file, and log from the terminal.

## Local URL

```text
http://127.0.0.1:8088
```

## Safety boundary

Phase 13AW is read-only.

Phase 13AW does not delete the real generated application.

Phase 13AW does not overwrite the real generated application.

Phase 13AW does not call live providers.

Phase 13AW does not call external systems.

Phase 13AW does not execute arbitrary shell commands from the UI.

Phase 13AW does not apply factory self-modifications.

Phase 13AW does not merge, tag, or release automatically.

## Portal sections

```text
factory_health
phase_status
evidence_summary
standards_summary
self_healing_summary
agentic_threat_summary
handover_summary
safe_command_catalog
```

## Operator model

The first portal phase is display-only. It shows:

```text
factory health
latest phase evidence
standards matrix status
self-healing repair catalog status
low-risk repair status
agentic threat-test status
handover replay status
safe command descriptions
```

Later phases may add controlled execution buttons through a governed command gateway. Arbitrary shell execution must remain blocked.

## Start command

```bash
python scripts/start_factory_operator_portal.py --host 127.0.0.1 --port 8088
```

## Governance improvement introduced

Phase 13AV added deterministic local agentic-AI threat tests. Phase 13AW makes the factory presentable and usable through a browser-based local operator portal foundation while preserving strict read-only governance.
