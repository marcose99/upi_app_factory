# API Test Commands

Evidence labels: MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA

```bash
curl -s http://127.0.0.1:8000/health | jq .
curl -s http://127.0.0.1:8000/ready | jq .
curl -s http://127.0.0.1:8000/disputes/mock-failed-transactions | jq .
curl -s -X POST http://127.0.0.1:8000/disputes/cases/from-failed-transaction \
  -H "Content-Type: application/json" \
  -d '{"transaction_id":"SYN-UPI-TXN-0001","created_by":"TECHNICAL_REVIEWER"}' | jq .
```
