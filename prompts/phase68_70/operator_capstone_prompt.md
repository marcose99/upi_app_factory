# Phase 68-70 Operator Capstone Prompt

Run the local capstone with a fresh runtime root:

```bash
bin/upi-app-factory-capstone --runtime-root /tmp/upi-phase68-70-capstone
```

Then validate it:

```bash
python3 scripts/validate_phase68_70_consolidated_capstone.py --runtime-root /tmp/upi-phase68-70-capstone
```

Use fictional data only. Keep live integrations disabled. Do not claim official certification, regulatory approval, production readiness or live payment readiness. Escalate protected actions to accountable humans outside the automated demo.

{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}
{{ include: prompts/_contracts/generated_application_quality_contract.md }}

{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}
