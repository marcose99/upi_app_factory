from __future__ import annotations

TRANSITION_TABLE = {
    "received": ("validated", "rejected"),
    "validated": ("evidence_pending",),
    "evidence_pending": ("investigation",),
    "investigation": ("resolution_proposed",),
    "resolution_proposed": ("resolved", "rejected"),
    "resolved": ("closed",),
    "rejected": ("closed",),
    "closed": (),
}
DOMAIN_STATES = ('received', 'validated', 'evidence_pending', 'investigation', 'resolution_proposed', 'resolved', 'rejected', 'closed')
