# Environment Specification

Recommended environment:
- Ubuntu 22.04 LTS or equivalent Linux environment
- Python 3.10.x
- Git
- Bash
- Local filesystem write access
- No live payment credentials required

Python capabilities:
- FastAPI
- Pydantic
- pytest
- ruff
- mypy

Network boundary:
- The generated application does not need live NPCI, RBI, bank, PSP, ODR,
  settlement, or payment-rail network access.
- Any such integration must remain blocked until a future explicitly approved
  live-integration phase, which is outside the current project boundary.

Data boundary:
- Do not use real customer data.
- Use synthetic/local test data only.
