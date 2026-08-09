# Support

UPI App Factory is provided as a public local-first engineering project.

## Before asking for help

1. Read `README.md`.
2. Follow `docs/handover/QUICKSTART.md`.
3. Check `docs/handover/TROUBLESHOOTING.md`.
4. Confirm your platform against `config/supported_platforms.yaml`.
5. Record the exact revision with:
   ```bash
   git rev-parse HEAD
   git rev-parse HEAD^{tree}
   ```

## Where to report a problem

Use GitHub Issues for:
- reproducible startup/runtime defects;
- documentation errors;
- Docker/local recipient problems;
- enhancement proposals.

Please include the platform, exact revision, command used, expected behavior and sanitized error output.

For vulnerabilities or anything involving secrets/security-sensitive exploit details, follow `SECURITY.md` instead of posting details publicly.

## Scope boundary

Community support covers the documented local/mock routes. Production deployment, real payment/provider connectivity, regulatory certification, enterprise IAM and production SLO operation are outside the supported public evaluation scope.
