from __future__ import annotations

import hashlib
from pathlib import Path
import tarfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_directory(
    source: Path,
    destination: Path,
) -> tuple[Path, Path]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(source))
    checksum = destination.with_suffix(destination.suffix + ".sha256")
    checksum.write_text(
        f"{sha256(destination)}  {destination.name}\n",
        encoding="utf-8",
    )
    return destination, checksum
