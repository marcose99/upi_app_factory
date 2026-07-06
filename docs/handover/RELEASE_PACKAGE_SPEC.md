# Release Package Specification

Future command:

```bash
./factory package-handover
```

Expected output:

```text
release_packages/
└── upi_dispute_resolution_factory_<tag>_handover/
    ├── README_HANDOVER.md
    ├── QUICKSTART.md
    ├── ENVIRONMENT_SPEC.md
    ├── COMMAND_REFERENCE.md
    ├── FACTORY_ARCHITECTURE.md
    ├── GENERATED_APPLICATION_GUIDE.md
    ├── GOVERNANCE_AND_AUDIT_GUIDE.md
    ├── TROUBLESHOOTING.md
    ├── VALIDATION_REPORT.json
    ├── HANDOVER_MANIFEST.json
    ├── checksums.sha256
    ├── portals/
    └── evidence/
```

The package must include:
- release tag
- source commit
- validation summary
- portal copies
- evidence ledgers
- generated app path
- known limitations
- truth boundary
