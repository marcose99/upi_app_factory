# Handover Release Package Runbook

## Objective

Create a self-contained handover bundle.

## Package contents

- handover docs
- deployment guides
- runbooks
- validation report
- portals
- runtime ledgers
- self-correction ledgers
- generated app evidence
- checksums
- release tag and commit id

## Future command

```bash
./factory package-handover
```

Until then, create the package using a governed script that copies the required files
into `release_packages/`.
