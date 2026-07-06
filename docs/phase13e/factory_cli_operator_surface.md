# Phase 13E — Factory CLI Operator Command Surface

Phase 13E adds a stable local operator command surface for the governed UPI dispute resolution factory.

## Root command

```bash
./factoryctl status
```

The repository already contains a `factory/` directory, so the safe root command is `./factoryctl` rather than `./factory`.

## Truth boundary

Phase 13E does **not** activate LangGraph/OpenAI execution. Default execution remains local deterministic. LangGraph/OpenAI adapter capability remains detected and policy-gated through the Phase 13D adapter layer.

## Commands

```bash
./factoryctl status
./factoryctl adapters
./factoryctl validate --quick
./factoryctl validate
./factoryctl portals
./factoryctl handover
./factoryctl logs
```

## Operator intent

The CLI reduces handover friction by giving operators one memorable command surface instead of requiring them to know every underlying script. It preserves the existing governed evidence and validation model rather than bypassing it.

## Safety model

- Read-only commands: `status`, `handover`, `logs`
- Local deterministic evidence generation: `adapters`, `portals`
- Local validation only: `validate --quick`, `validate`
- No network access is required by default
- No secret is required by default
- No external LLM execution is claimed by this phase
