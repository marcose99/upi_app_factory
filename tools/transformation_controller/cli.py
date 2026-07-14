from __future__ import annotations

import sys
from typing import Sequence

from tools.lifecycle_orchestrator import cli as lifecycle_cli
from tools.transformation_controller import (
    phase46a,
    phase46b,
    phase46c,
    phase46d,
    phase46f,
)
from tools.identity_compat import promote_legacy_environment_aliases


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

PHASE46D_ACTIONS = {
    "resolve-identity",
    "execute-compatibility-wave",
    "verify-compatibility-run",
    "compatibility-run-status",
}
PHASE46F_ACTIONS = {
    "implement-display-identity-contract",
    "verify-display-identity-contract",
    "display-identity-status",
}



def main(argv: Sequence[str] | None = None) -> int:
    promote_legacy_environment_aliases()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "lifecycle":
        return lifecycle_cli.main(arguments)
    if len(arguments) >= 2 and arguments[0] == "transform":
        if arguments[1] in PHASE46B_ACTIONS:
            return phase46b.main(arguments)
        if arguments[1] in PHASE46C_ACTIONS:
            return phase46c.main(arguments)
        if arguments[1] in PHASE46D_ACTIONS:
            return phase46d.main(arguments)
        if arguments[1] in PHASE46F_ACTIONS:
            return phase46f.main(arguments)
    return phase46a.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
