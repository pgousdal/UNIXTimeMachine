from dataclasses import dataclass
from enum import Enum

class Track(str, Enum):
    UNIX = "unix"
    UNIXISH = "unixish"
    BEYOND_UNIX = "beyond-unix"

class SessionState(str, Enum):
    REQUESTED = "requested"
    ALLOCATED = "allocated"
    STARTING = "starting"
    READY = "ready"
    ACTIVE = "active"
    STOPPING = "stopping"
    RESETTING = "resetting"
    RELEASED = "released"
    FAILED = "failed"

@dataclass(frozen=True)
class MuseumSystem:
    id: str
    name: str
    track: Track
    year: int
    emulator_family: str
    public_eligible: bool
