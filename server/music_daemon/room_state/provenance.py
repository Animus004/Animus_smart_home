"""
State Provenance Taxonomy for Animus Smart Room.
Authoritatively classifies the epistemological origin of every RoomState field.
"""

from enum import Enum

class Provenance(str, Enum):
    """
    Provenance classification:
    - OBSERVED: Directly measured from physical sensors or active hardware interfaces.
    - DERIVED: Deterministically computed from one or more OBSERVED fields.
    - STALE: Previously valid observation or derivation that has exceeded its TTL window.
    - UNKNOWN: Unreachable, uninitialized, or failed query with no valid data.
    """
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
