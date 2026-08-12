from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

class Track(str, Enum):
    UNIX = "unix"
    UNIXISH = "unixish"
    BEYOND_UNIX = "beyond-unix"

class SessionState(str, Enum):
    REQUESTED = "requested"
    ALLOCATED = "allocated"
    PREPARING = "preparing"
    STARTING = "starting"
    READY = "ready"
    ACTIVE = "active"
    STOPPING = "stopping"
    RESETTING = "resetting"
    RELEASED = "released"
    FAILED = "failed"


TRANSITIONS = {
    SessionState.REQUESTED: {SessionState.ALLOCATED, SessionState.FAILED},
    SessionState.ALLOCATED: {SessionState.PREPARING, SessionState.FAILED},
    SessionState.PREPARING: {SessionState.STARTING, SessionState.FAILED},
    SessionState.STARTING: {SessionState.READY, SessionState.STOPPING, SessionState.FAILED},
    SessionState.READY: {SessionState.ACTIVE, SessionState.STOPPING, SessionState.FAILED},
    SessionState.ACTIVE: {SessionState.READY, SessionState.STOPPING, SessionState.FAILED},
    SessionState.STOPPING: {SessionState.RESETTING, SessionState.FAILED},
    SessionState.FAILED: {SessionState.STOPPING, SessionState.RESETTING},
    SessionState.RESETTING: {SessionState.RELEASED, SessionState.FAILED},
    SessionState.RELEASED: set(),
}


@dataclass
class SessionRecord:
    session_id: str
    system_id: str
    state: str = SessionState.REQUESTED.value
    created_at: str = ""
    updated_at: str = ""
    supervisor_pid: int | None = None
    supervisor_start_ticks: int | None = None
    emulator_pid: int | None = None
    emulator_start_ticks: int | None = None
    socket_path: str | None = None
    workspace: str | None = None
    transcript: str | None = None
    ready_at: str | None = None
    attached_at: str | None = None
    last_activity_at: str | None = None
    stop_reason: str | None = None
    failure: str | None = None
    exit_code: int | None = None
    golden_sha256: dict[str, str] = field(default_factory=dict)
    copy_methods: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionRecord":
        known = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in known})

@dataclass(frozen=True)
class MuseumSystem:
    id: str
    name: str
    track: Track
    year: int
    emulator_family: str
    public_eligible: bool
