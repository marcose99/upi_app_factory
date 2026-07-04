from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json


def main() -> None:
    out = Path("workspace/release_packs/latest")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "LOCAL_BASELINE_RELEASE_PACK",
        "claims": [
            "Mock-safe local baseline generated",
            "Not NPCI certified",
            "Not production deployed",
            "No real UPI/bank/payment calls",
        ],
    }
    (out / "release_readiness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "KNOWN_LIMITATIONS.md").write_text(
        "# Known Limitations\n\n- Local factory baseline only.\n- No real UPI/NPCI/bank integration.\n- Synthetic workflow model.\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": True, "release_pack": str(out)}, indent=2))


if __name__ == "__main__":
    main()
