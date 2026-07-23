from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


FORBIDDEN = "Factory" + "FromNothing"
LEGACY_REPOSITORY = "upi_dispute_resolution" + "_factory"
LEGACY_KEBAB = "upi-dispute-resolution" + "-factory"
LEGACY_HUMAN = "UPI Dispute Resolution" + " Factory"
LEGACY_ENV_PREFIX = "UPI_DISPUTE_RESOLUTION" + "_FACTORY"
CANONICAL_REPOSITORY = "upi_app_factory"
CANONICAL_HUMAN = "UPI App Factory"


def tracked_files(root: Path) -> list[Path]:
    raw = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    ).stdout
    return [
        root / item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\x00")
        if item
    ]


def allowed_deferred(line: str, legacy_checkout_root: Path) -> bool:
    fragments = (
        str(legacy_checkout_root),
        f"github.com/legacy-owner/{LEGACY_REPOSITORY}",
        f"github.com/legacy-owner/{LEGACY_REPOSITORY}.git",
    )
    return any(fragment in line for fragment in fragments)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--legacy-checkout-root", type=Path)
    parsed = parser.parse_args()
    root = parsed.project_root.resolve()
    legacy_root = (
        parsed.legacy_checkout_root.resolve()
        if parsed.legacy_checkout_root is not None
        else Path(os.environ.get("UPI_APP_FACTORY_SOURCE_REPO", root)).resolve()
    )

    violations: list[str] = []
    canonical_hits = 0
    generated_app_hits = 0
    for path in tracked_files(root):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if FORBIDDEN in relative:
            violations.append(f"forbidden project label in path: {relative}")
        if CANONICAL_REPOSITORY in relative:
            canonical_hits += 1
        if "upi_dispute_resolution" in relative:
            generated_app_hits += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if FORBIDDEN in text:
            violations.append(f"forbidden project label in content: {relative}")
        if CANONICAL_REPOSITORY in text or CANONICAL_HUMAN in text:
            canonical_hits += 1
        if "upi_dispute_resolution" in text:
            generated_app_hits += 1
        for number, line in enumerate(text.splitlines(), start=1):
            for token in (
                LEGACY_REPOSITORY,
                LEGACY_KEBAB,
                LEGACY_HUMAN,
                LEGACY_ENV_PREFIX,
            ):
                if token in line and not allowed_deferred(line, legacy_root):
                    violations.append(
                        f"non-deferred legacy identity: {relative}:{number}"
                    )
    if canonical_hits == 0:
        violations.append("canonical identity is absent")
    if generated_app_hits == 0:
        violations.append("generated application identity was not preserved")
    if violations:
        raise SystemExit("\n".join(sorted(set(violations))))
    print(
        "Phase 47B validation passed: logical identity canonicalized; "
        "forbidden project label removed; generated application identity "
        "preserved; physical checkout and remote references deferred."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
