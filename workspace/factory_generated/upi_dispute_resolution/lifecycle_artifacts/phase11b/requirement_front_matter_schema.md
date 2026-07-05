# Requirement Front Matter Schema

Labels:
- PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE
- EXTERNAL_ECOSYSTEM_MOCK_ONLY
- SYNTHETIC_DATA_ONLY
- REAL_PAYMENT_PROCESSING_FORBIDDEN
- PRODUCTION_CLAIMS_FORBIDDEN

Required front matter:

```yaml
requirement_id: REQ-PAYMENT-001
app_id: upi_dispute_resolution
domain: payments
generation_mode: real_local_primary_payment_application_with_mock_ecosystem
primary_application_real: true
external_ecosystem_mock_only: true
synthetic_data_only: true
external_payment_connectivity_allowed: false
real_payment_processing_allowed: false
production_claims_allowed: false
```

The requirement intake gate must reject documents that attempt to enable
external payment connectivity, real payment processing, real customer data,
or unsupported certification/readiness claims.
