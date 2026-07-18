from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/governed-ci.yml",
    "docs/governance/repository_governance.md",
    "requirements/ci-lock.txt",
    "scripts/validate_phase63_repository_governance.py",
    "tests/test_phase63_repository_governance.py",
]
EXPECTED_JOBS = [
    "governance_policy:",
    "ruff:",
    "mypy:",
    "focused_tests:",
    "full_regression:",
]
EXPECTED_NAMES = [
    "name: Governance policy",
    "name: Ruff",
    "name: MyPy",
    "name: Focused tests",
    "name: Full regression",
]

def fail(message: str) -> None:
    raise SystemExit(message)

def main() -> int:
    missing = [item for item in REQUIRED if not (ROOT / item).is_file()]
    if missing:
        fail("missing governance files: " + ", ".join(missing))

    workflow = (
        ROOT / ".github/workflows/governed-ci.yml"
    ).read_text(encoding="utf-8")
    if "pull_request_target:" in workflow:
        fail("pull_request_target is prohibited")
    if "permissions: write-all" in workflow:
        fail("write-all permissions are prohibited")
    if "permissions:\n  contents: read" not in workflow:
        fail("workflow must use repository-level contents: read")
    if "persist-credentials: false" not in workflow:
        fail("checkout credentials must not persist")
    if "${{ secrets." in workflow:
        fail("governed CI must not consume repository secrets")
    if "timeout-minutes:" not in workflow:
        fail("jobs must have explicit timeouts")
    for token in EXPECTED_JOBS + EXPECTED_NAMES:
        if token not in workflow:
            fail(f"workflow token missing: {token}")

    uses = re.findall(r"uses:\s*([^\s]+)", workflow)
    if not uses:
        fail("workflow contains no actions")
    for item in uses:
        match = re.fullmatch(r"(actions/[^@]+)@([0-9a-f]{40})", item)
        if not match:
            fail(f"action is not pinned to a full SHA: {item}")

    codeowners = (
        ROOT / ".github/CODEOWNERS"
    ).read_text(encoding="utf-8")
    if "* @marcose99" not in codeowners:
        fail("default CODEOWNER is missing")
    if ".github/ @marcose99" not in codeowners:
        fail(".github ownership is missing")

    template = (
        ROOT / ".github/pull_request_template.md"
    ).read_text(encoding="utf-8")
    for heading in [
        "## Purpose",
        "## Governed scope",
        "## Validation evidence",
        "## Security and data handling",
        "## Human decisions",
        "## Residual risks",
    ]:
        if heading not in template:
            fail(f"pull-request template heading missing: {heading}")

    lock_lines = [
        line.strip()
        for line in (ROOT / "requirements/ci-lock.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    if not lock_lines:
        fail("CI dependency lock is empty")
    for line in lock_lines:
        if line.startswith("-e ") or "file:" in line or "git+" in line:
            fail(f"non-reproducible CI dependency: {line}")

    report = {
        "status": "passed",
        "required_files": REQUIRED,
        "pinned_actions": uses,
        "expected_check_names": EXPECTED_NAMES,
        "default_code_owner": "@marcose99",
        "independent_review_limitation": (
            "A second authorized reviewer is required for genuinely "
            "independent approval; CODEOWNERS alone cannot create one."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
