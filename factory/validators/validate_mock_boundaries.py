from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
THIS_FILE = Path(__file__).resolve()

SCAN_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

# These are intentionally forbidden real-boundary markers.
# This validator file is excluded from scanning to avoid self-matching.
FORBIDDEN_REAL_BOUNDARY_MARKERS = [
    "npci.org.in/api",
    "upi.production",
    "real_bank_api",
    "settlement.production",
]

REQUIRED_EVIDENCE_LABELS = [
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
]


def should_scan(path: Path) -> bool:
    resolved = path.resolve()

    if resolved == THIS_FILE:
        return False

    if path.suffix not in SCAN_SUFFIXES:
        return False

    relative_parts = path.relative_to(PROJECT_ROOT).parts
    if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
        return False

    return True


def iter_scan_files() -> list[Path]:
    return sorted(
        path
        for path in PROJECT_ROOT.rglob("*")
        if path.is_file() and should_scan(path)
    )


def main() -> int:
    errors: list[str] = []
    corpus_parts: list[str] = []

    for path in iter_scan_files():
        relative_path = path.relative_to(PROJECT_ROOT)

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        corpus_parts.append(text)

        for marker in FORBIDDEN_REAL_BOUNDARY_MARKERS:
            if marker in text:
                errors.append(
                    f"forbidden real boundary marker {marker} in {relative_path}"
                )

    corpus = "\n".join(corpus_parts)

    for label in REQUIRED_EVIDENCE_LABELS:
        if label not in corpus:
            errors.append(f"required evidence label missing: {label}")

    result = {
        "passed": not errors,
        "errors": errors,
    }

    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
