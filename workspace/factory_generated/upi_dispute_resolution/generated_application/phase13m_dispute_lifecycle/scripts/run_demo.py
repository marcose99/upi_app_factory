from __future__ import annotations

import json

from phase13m_dispute_lifecycle_app.api import create_case, progress_case_to_resolution

payload = {
    "transaction_id": "TXN-20260706-LIFE-DEMO",
    "payer_vpa": "payer@upi",
    "payee_vpa": "merchant@upi",
    "amount_paise": 9900,
    "evidence_refs": ["demo:evidence", "demo:customer-note"],
}

created = create_case(payload)
resolved = progress_case_to_resolution(str(created["case_id"]))
print(json.dumps(resolved, indent=2, sort_keys=True))
