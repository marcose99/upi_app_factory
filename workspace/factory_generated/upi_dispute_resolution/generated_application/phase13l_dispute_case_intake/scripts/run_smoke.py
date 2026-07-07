from __future__ import annotations

import json

from phase13l_dispute_case_intake_app.api import create_dispute_case

payload = {
    "transaction_id": "TXN-20260706-SMOKE",
    "payer_vpa": "payer@upi",
    "payee_vpa": "merchant@upi",
    "amount_paise": 9900,
    "rail": "UPI",
    "category": "FAILED_TRANSACTION",
    "evidence_refs": ["smoke-test:evidence"],
}

print(json.dumps(create_dispute_case(payload), indent=2, sort_keys=True))
