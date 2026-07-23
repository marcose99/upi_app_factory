# Quickstart for a New Machine

## 1. Clone and select release

```bash
git clone <repo-url>
cd upi_app_factory
git checkout <validated-release-tag>
```

## 2. Start the operator portal

```bash
./run_factory.sh --no-browser
```

This is the canonical clean-clone command. It creates or reuses `.venv`,
installs/verifies `requirements-recipient.txt`, initializes `.var/upi_app_factory`
with `runs`, `portfolio`, `runtime`, `logs`, `downloads`, and `evidence`, waits
for `/health`, and prints the verified `/operator-ui/` URL.

Use `./run_factory.sh --port 0 --url-file .var/upi_app_factory/operator_url.txt --no-browser`
to avoid a port conflict deterministically.

## 3. Validate baseline

```bash
python scripts/validate_phase13c_agent_runtime_foundation.py
python scripts/validate_phase13c_self_correction_governance.py
python scripts/validate_phase13b_generated_application.py
python scripts/validate_phase13b_progress_portal_observability.py
python -m pytest -q
```

## 4. Open portal

```text
http://127.0.0.1:8036/operator-ui/
```

The portal includes a Use Sample Requirements control backed by
`examples/requirements/01_upi_failed_debit_no_credit.md`; pasted/uploaded
requirements remain supported by the intake contract.
