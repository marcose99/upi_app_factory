from __future__ import annotations

import sys
from typing import Sequence

from tools.transformation_controller import phase46a, phase46b, phase46c


PHASE46B_ACTIONS = {
    "execute",
    "execution-status",
    "replay",
}

PHASE46C_ACTIONS = {
    "plan-identity-migration",
    "migration-plan-status",
    "verify-migration-plan",
}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) >= 2 and arguments[0] == "transform":
        if arguments[1] in PHASE46B_ACTIONS:
            return phase46b.main(arguments)
        if arguments[1] in PHASE46C_ACTIONS:
            return phase46c.main(arguments)
    return phase46a.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())

