# Secret and Environment Guard Policy — upi_dispute_resolution

Labels: SECRET_EXFILTRATION_BLOCKED, FAIL_CLOSED, HUMAN_APPROVAL_REQUIRED

Agents must not read, print, copy, infer, transform, or request API keys,
tokens, passwords, private keys, .env files, SSH keys, cloud credentials, live
banking credentials, live payment credentials, or real customer data.

Synthetic placeholders are allowed only when clearly labelled as not usable.
Any suspected secret access stops the run and records a decision-log event.
