from __future__ import annotations

import sys
from typing import Sequence

from tools.transformation_controller import phase46a, phase46b


PHASE46B_ACTIONS = {
    "execute",
    "execution-status",
    "replay",
}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if (
        len(arguments) >= 2
        and arguments[0] == "transform"
        and arguments[1] in PHASE46B_ACTIONS
    ):
        return phase46b.main(arguments)
    return phase46a.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())

