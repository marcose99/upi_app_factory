# Deployment Boundaries and Non-Claims

> **Status:** Canonical current-state documentation
> **Purpose:** State what local/native/container routes are supported and what is not claimed.
> **Audience:** operators, recipients, architects and reviewers
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 26514:2022
- ISO/IEC 20000-1:2018 and SRE practices

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Supported

- Native Linux recipient route through `./run_factory.sh`
- Docker/Compose route through `docker compose up --build`
- Loopback-only local publication
- Local/mock/default-off payment and LLM behavior

## Not claimed

- Production deployment approval
- Live UPI/payment processing
- Native Windows or macOS support
- Kubernetes requirement/support as an acceptance prerequisite
- High availability, production TLS/ingress, production secret store or enterprise SSO
- Regulatory or standards certification

See [Local and Docker Deployment](LOCAL_AND_DOCKER_DEPLOYMENT.md).

## Legacy Phase 13C compatibility contract

For the accepted local/mock boundary there is **no live payment rail integration** and **no real customer data** is required or authorized for acceptance. These phrases are retained because the historical validator encodes the same safety boundary.
