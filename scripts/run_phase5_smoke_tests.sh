#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

curl -s "$BASE_URL/health" | jq .
curl -s "$BASE_URL/ready" | jq .
curl -s "$BASE_URL/disputes/mock-failed-transactions" | jq .

created_case="$(
  curl -s -X POST "$BASE_URL/disputes/cases/from-failed-transaction" \
    -H "Content-Type: application/json" \
    -d '{"transaction_id":"SYN-UPI-TXN-0001","created_by":"TECHNICAL_REVIEWER"}'
)"

echo "$created_case" | jq .
case_id="$(echo "$created_case" | jq -r '.case_id')"

curl -s -X POST "$BASE_URL/disputes/cases/${case_id}/actions" \
  -H "Content-Type: application/json" \
  -d '{"action":"ASSIGN_REVIEWER","reviewer":"GOVERNANCE_REVIEWER","notes":"Smoke test review."}' | jq .
