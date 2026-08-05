#!/usr/bin/env sh
set -eu
python -m uvicorn app.upi_failed_debit_dispute.interfaces.api.main:app --host 127.0.0.1 --port 8000
