from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import yaml

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
PINNED_CHECKOUT = "actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd"
PINNED_SETUP = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
EXACT_REVISION = "${{ github.event.pull_request.head.sha || github.sha }}"
EXPECTED_JOBS = {
    "governance_policy": ("Governance policy", 10),
    "public_clone_hygiene": ("Public clone hygiene", 15),
    "ruff": ("Ruff", 15),
    "mypy": ("MyPy", 30),
    "focused_tests": ("Focused tests", 35),
    "docker_platform_contract": ("Docker platform contract", 20),
    "full_regression": ("Full regression", 60),
}
REVISION_ENV = {
    "EXPECTED_SHA": EXACT_REVISION,
    "PR_HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
    "PR_BASE_SHA": "${{ github.event.pull_request.base.sha }}",
}
EXACT_ASSERT = 'set -euo pipefail\nactual="$(git rev-parse HEAD)"\ntest "${#EXPECTED_SHA}" -eq 40\ncase "$EXPECTED_SHA" in\n  *[!0-9a-f]*) echo "invalid expected SHA" >&2; exit 1 ;;\nesac\ntest "$actual" = "$EXPECTED_SHA"\nprintf "validated_sha=%s\\npr_head_sha=%s\\npr_base_sha=%s\\n" "$actual" "$PR_HEAD_SHA" "$PR_BASE_SHA"\n'


def fail(message: str) -> None:
    raise SystemExit(message)


def _map(v: object) -> dict[str, Any] | None:
    return v if isinstance(v, dict) else None


def _secrets(v: object) -> bool:
    if isinstance(v, str):
        return "${{ secrets." in v
    if isinstance(v, list):
        return any(_secrets(x) for x in v)
    if isinstance(v, dict):
        return any(_secrets(k) or _secrets(x) for k, x in v.items())
    return False


def _validate_workflow_structure(text: str) -> list[str]:
    e = []
    if "pull_request_target:" in text:
        e.append("pull_request_target is prohibited")
    try:
        p = yaml.safe_load(text)
    except yaml.YAMLError as x:
        return [f"workflow YAML is invalid: {x}"]
    if not isinstance(p, dict):
        return ["workflow root must be mapping"]
    if _map(p.get("permissions")) != {"contents": "read"}:
        e.append("workflow permissions must be exactly contents: read")
    if _secrets(p):
        e.append("governed CI must not consume repository secrets")
    jobs = _map(p.get("jobs"))
    if jobs is None:
        return e + ["workflow jobs mapping missing"]
    if set(jobs) != set(EXPECTED_JOBS):
        e.append("governed job IDs changed")
    for jid, (name, timeout) in EXPECTED_JOBS.items():
        job = _map(jobs.get(jid))
        if job is None:
            e.append(f"job {jid} missing")
            continue
        if job.get("name") != name:
            e.append(f"job {jid} display name changed")
        if job.get("runs-on") != "ubuntu-latest":
            e.append(f"job {jid} runner changed")
        if job.get("timeout-minutes") != timeout:
            e.append(f"job {jid} timeout changed")
        if "permissions" in job:
            e.append(f"job {jid} permission override")
        if "if" in job or job.get("continue-on-error") is not None:
            e.append(f"job {jid} failure semantics weakened")
        steps = job.get("steps")
        if not isinstance(steps, list) or len(steps) < 2:
            e.append(f"job {jid} security preamble missing")
            continue
        for number, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                e.append(f"job {jid} step {number} is not a mapping")
                continue
            if "if" in step:
                e.append(f"job {jid} step {number} must not be conditional")
            if step.get("continue-on-error") is not None:
                e.append(f"job {jid} step {number} weakens failure semantics")
        co = _map(steps[0])
        ass = _map(steps[1])
        if (
            co is None
            or co.get("name") != "Checkout exact revision"
            or co.get("uses") != PINNED_CHECKOUT
        ):
            e.append(f"job {jid} checkout contract changed")
        else:
            w = _map(co.get("with"))
            if (
                w is None
                or w.get("ref") != EXACT_REVISION
                or w.get("fetch-depth") != 0
                or w.get("persist-credentials") is not False
            ):
                e.append(f"job {jid} checkout options changed")
        if ass is None or ass.get("name") != "Assert exact checked out revision":
            e.append(f"job {jid} assertion step changed")
        else:
            if _map(ass.get("env")) != REVISION_ENV:
                e.append(f"job {jid} assertion env changed")
            if not isinstance(ass.get("run"), str) or ass["run"].strip() != EXACT_ASSERT.strip():
                e.append(f"job {jid} assertion program changed")
        for st in steps:
            if isinstance(st, dict) and isinstance(st.get("uses"), str):
                u = st["uses"]
                if u not in {PINNED_CHECKOUT, PINNED_SETUP}:
                    e.append(f"job {jid} unapproved action: {u}")
                if re.fullmatch(r"actions/[^@]+@[0-9a-f]{40}", u) is None:
                    e.append(f"job {jid} action not full-SHA pinned")
    return e


def main() -> int:
    missing = [x for x in REQUIRED if not (ROOT / x).is_file()]
    if missing:
        fail("missing governance files: " + ", ".join(missing))
    errors = _validate_workflow_structure((ROOT / ".github/workflows/governed-ci.yml").read_text())
    if errors:
        fail("workflow governance validation failed: " + "; ".join(errors))
    codeowners = (ROOT / ".github/CODEOWNERS").read_text()
    template = (ROOT / ".github/pull_request_template.md").read_text()
    if (
        "* @upi-app-factory-maintainers" not in codeowners
        or ".github/ @upi-app-factory-maintainers" not in codeowners
    ):
        fail("CODEOWNERS contract changed")
    for h in [
        "## Purpose",
        "## Governed scope",
        "## Validation evidence",
        "## Security and data handling",
        "## Human decisions",
        "## Residual risks",
    ]:
        if h not in template:
            fail(f"pull-request template heading missing: {h}")
    lines = [
        x.strip() for x in (ROOT / "requirements/ci-lock.txt").read_text().splitlines() if x.strip()
    ]
    if not lines or any(x.startswith("-e ") or "file:" in x or "git+" in x for x in lines):
        fail("CI dependency lock is not reproducible")
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_control_plane_authority_policy.py"),
            "--repo",
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode:
        fail("control-plane authority validation failed: " + r.stdout.strip())
    print(
        json.dumps(
            {
                "status": "passed",
                "governed_jobs": EXPECTED_JOBS,
                "pinned_actions": [PINNED_CHECKOUT, PINNED_SETUP],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
