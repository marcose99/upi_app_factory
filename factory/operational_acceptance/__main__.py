"""Command-line entrypoint for deterministic operational acceptance."""

import sys

from .clean_room import main as clean_room_main
from .failure_recovery import main as failure_recovery_main
from .harness import main as operational_acceptance_main


if sys.argv[1:2] == ["clean-room"]:
    raise SystemExit(clean_room_main(sys.argv[2:]))
if sys.argv[1:2] == ["failure-recovery"]:
    raise SystemExit(failure_recovery_main(sys.argv[2:]))
raise SystemExit(operational_acceptance_main(sys.argv[1:]))
