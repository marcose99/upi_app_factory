# Supply Chain and Dependencies

The factory recipient route uses exact bootstrap and recipient locks. The authoritative generated application separately owns exact bootstrap/runtime-test locks, a machine-checkable dependency contract, a clean-room bootstrap and a fail-closed dependency validator.

Qualification includes installed-closure checks, `pip check`, known-vulnerability audit support and CycloneDX SBOM evidence. First-party local source is handled separately from PyPI third-party vulnerability lookup.

Generated runtime processes sanitize credential-like environment values and reassert local/mock/no-real-payment safety flags.

These controls do not constitute regulatory certification or production deployment approval.
