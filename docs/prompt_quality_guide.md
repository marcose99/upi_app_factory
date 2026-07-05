# Prompt Quality Guide for FactoryFromNothing

This guide defines prompt statements that produce better outputs for this project.
Use these patterns when asking for architecture, code, tests, governance, validation, debugging, or release work.

## High-impact prompt template

```text
Project: /home/marcose/projects/upi_dispute_resolution_factory
Current stable branch: main
Current restore point: <tag>
Current HEAD: <commit>

Goal:
<describe the exact phase or fix>

Non-negotiable constraints:
- Beginner-readable and debug-friendly code.
- Deterministic scripts where practical.
- No hidden production dependency behind mock boundaries.
- Preserve honesty labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA.
- Every generated artifact must be traceable to requirement/task/policy/evidence where applicable.
- Do not merge or tag unless explicitly asked.

Required output:
- Explain the design briefly.
- Provide an executable script.
- Include validation commands.
- Include rollback guidance.
- Include what success should look like.
```

## Prompt statements that improve code quality

Use these exact statements when asking for code:

```text
Generate beginner-readable, debug-friendly Python 3.10 code. Prefer clear names, small functions, explicit validation, actionable errors, and simple control flow. Avoid clever abstractions unless they are necessary.
```

```text
Before finalizing the code, review it as a maintainer and as a beginner. Remove unnecessary complexity. Add comments only where they explain intent, policy, or non-obvious decisions.
```

```text
Make the script safe and deterministic: preflight checks first, write files predictably, fail loudly on unsafe state, and avoid destructive commands unless explicitly requested.
```

```text
Add validation that proves the change works. The validation should be executable from the terminal and should fail with useful messages if the expected evidence is missing.
```

## Prompt statements that improve architecture quality

```text
Act as a governed agentic software factory architect. Propose multiple viable designs, compare pros and cons, select the best option, and explain why it fits the current lightweight-but-production-disciplined stage.
```

```text
Separate current implementation from future enterprise scale. Do not over-engineer now, but keep interfaces modular so components can later be replaced with enterprise-grade infrastructure.
```

```text
Show module-level design, artifact flow, validation flow, evidence flow, and human review points. Keep the explanation understandable to a beginner without weakening the architecture.
```

## Prompt statements that improve governance quality

```text
For every generated artifact, include requirement IDs, task IDs, policy IDs, evidence references, and honesty labels wherever applicable.
```

```text
Do not claim official compliance unless official sources are present and cited. Use MISSING_OFFICIAL_SOURCE when official sources are absent.
```

```text
Show what is real, what is synthetic, what is mocked, what is proven, and what remains a limitation.
```

## Prompt statements that improve debugging quality

```text
Diagnose from the pasted terminal output only. Identify the first failing command, the first meaningful error, likely root cause, safest next command, and expected good output.
```

```text
Do not suggest broad cleanup. Give the smallest safe fix first, then the validation command, then the rollback command.
```

```text
Explain the issue in two layers: beginner explanation first, maintainer-level detail second.
```

## Prompt statements that improve phase automation

```text
Provide a single executable bash script that creates a new branch, applies the phase, writes or updates files, runs focused tests, runs relevant make targets, commits the result, and stops before merge/tag.
```

```text
The script must be idempotent where practical, must fail on dirty tracked working tree, must print clear section headers, and must not hide validation failures.
```

```text
Include commands to inspect generated files and explain exactly what success means.
```

## Prompt statements that improve testing quality

```text
Add tests that prove the contract, not just the happy path. Include at least one negative test for missing required evidence or broken traceability when applicable.
```

```text
Prefer deterministic tests that run quickly on Python 3.10.12 without external services.
```

```text
Keep tests beginner-readable: arrange, act, assert; clear fixture names; direct assertions with helpful failure messages.
```

## Prompt statements that improve final review quality

```text
Before recommending merge/tag, cross-check git branch, git log, git tag, git status, all validation gates, generated evidence, and known limitations.
```

```text
Give a release-readiness answer with: passed items, remaining limitations, exact merge/tag commands, rollback command, and next recommended phase.
```

## Anti-prompts to avoid

Avoid vague prompts like:

```text
Make it better.
Fix everything.
Add agents.
Do it production grade.
Make it perfect.
```

Replace them with:

```text
Improve <specific area> by adding <specific artifact or behavior>, prove it with <specific validator/test>, preserve <specific constraints>, and stop before merge/tag.
```

## References

- OpenAI Prompt Engineering Guide: https://developers.openai.com/api/docs/guides/prompt-engineering
- OpenAI Reasoning Best Practices: https://developers.openai.com/api/docs/guides/reasoning-best-practices
- Google Engineering Practices: https://google.github.io/eng-practices/review/reviewer/standard.html
