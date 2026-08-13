from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from scripts.manifestlib import system_manifest
from scripts.utmlib import find_emulator, prepare_session, render_runtime, sha256


@dataclass(frozen=True)
class PreparedSession:
    workspace: Path
    command: list[str]
    readiness_patterns: list[str]
    copy_methods: list[str]
    golden_sha256: dict[str, str]


@dataclass(frozen=True)
class ShutdownProtocol:
    requires_guest_sync: bool
    monitor_enter: bytes
    monitor_prompt: bytes
    monitor_quit: bytes
    guest_procedure: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "requires_guest_sync": self.requires_guest_sync,
            "monitor_enter_hex": self.monitor_enter.hex(),
            "monitor_prompt_hex": self.monitor_prompt.hex(),
            "monitor_quit_hex": self.monitor_quit.hex(),
            "guest_procedure": self.guest_procedure,
        }


class Backend(ABC):
    @abstractmethod
    def prepare(self, system_id: str, session_id: str, root: Path) -> PreparedSession:
        raise NotImplementedError

    @abstractmethod
    def shutdown_protocol(self) -> ShutdownProtocol:
        """Describe the backend-specific, confirmation-gated stop handshake."""
        raise NotImplementedError


class SimhBackend(Backend):
    def __init__(self, guest_procedure: str | None = None):
        self.guest_procedure = guest_procedure

    def shutdown_protocol(self) -> ShutdownProtocol:
        return ShutdownProtocol(True, b"\x05", b"sim>", b"quit\r", self.guest_procedure)

    def prepare(self, system_id: str, session_id: str, root: Path) -> PreparedSession:
        _, manifest = system_manifest(system_id)
        workspace, methods = prepare_session(system_id, session_id, root)
        config = render_runtime(system_id, session_id, root)
        goldens = {disk["id"]: sha256(root / "golden" / system_id / disk["golden_filename"])
                   for disk in manifest["prepared"]["disks"]}
        return PreparedSession(workspace, [find_emulator(manifest), str(config)],
                               list(manifest["readiness"]["patterns"]), methods, goldens)


def backend_for(system_id: str) -> Backend:
    _, manifest = system_manifest(system_id)
    family = manifest.get("emulator", {}).get("family")
    if family == "simh":
        return SimhBackend(manifest.get("shutdown", {}).get("guest_procedure"))
    raise ValueError(f"no session backend adapter for emulator family: {family!r}")
