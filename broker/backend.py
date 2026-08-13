from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from scripts.manifestlib import system_manifest
from scripts.utmlib import find_emulator, prepare_session, render_runtime, sha256


@dataclass(frozen=True)
class ConsoleTransport:
    """Backend-selected guest console topology.

    Only stdio-pty is implemented by the production supervisor.  The external-pty
    description is an architecture contract for a future backend; selecting it
    currently fails closed rather than pretending that the transport exists.
    """

    kind: str
    authoritative: bool = True
    separate_diagnostics: bool = False

    @classmethod
    def stdio_pty(cls) -> "ConsoleTransport":
        return cls("stdio-pty")

    @classmethod
    def external_pty(cls) -> "ConsoleTransport":
        return cls("external-pty", separate_diagnostics=True)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "authoritative": self.authoritative,
            "separate_diagnostics": self.separate_diagnostics,
        }


@dataclass(frozen=True)
class PreparedSession:
    workspace: Path
    command: list[str]
    readiness_patterns: list[str]
    copy_methods: list[str]
    golden_sha256: dict[str, str]
    console: ConsoleTransport = field(default_factory=ConsoleTransport.stdio_pty)


@dataclass(frozen=True)
class ShutdownProtocol:
    """The qualified SIMH monitor shutdown driver configuration."""

    requires_guest_sync: bool
    monitor_enter: bytes
    monitor_prompt: bytes
    monitor_quit: bytes
    guest_procedure: str | None = None
    monitor_may_already_be_active: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "driver": "simh-monitor",
            "requires_guest_sync": self.requires_guest_sync,
            "monitor_enter_hex": self.monitor_enter.hex(),
            "monitor_prompt_hex": self.monitor_prompt.hex(),
            "monitor_quit_hex": self.monitor_quit.hex(),
            "guest_procedure": self.guest_procedure,
            "monitor_may_already_be_active": self.monitor_may_already_be_active,
        }


class Backend(ABC):
    @abstractmethod
    def prepare(self, system_id: str, session_id: str, root: Path) -> PreparedSession:
        raise NotImplementedError

    @abstractmethod
    def shutdown_protocol(self) -> ShutdownProtocol:
        """Describe the backend-specific, confirmation-gated stop handshake."""
        raise NotImplementedError

    def console_transport(self, prepared: PreparedSession) -> ConsoleTransport:
        """Return the prepared session's authoritative guest-console topology."""
        return prepared.console


class SimhBackend(Backend):
    def __init__(self, guest_procedure: str | None = None,
                 monitor_may_already_be_active: bool = False):
        self.guest_procedure = guest_procedure
        self.monitor_may_already_be_active = monitor_may_already_be_active

    def shutdown_protocol(self) -> ShutdownProtocol:
        return ShutdownProtocol(True, b"\x05", b"sim>", b"quit\r", self.guest_procedure,
                                self.monitor_may_already_be_active)

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
        shutdown = manifest.get("shutdown", {})
        return SimhBackend(shutdown.get("guest_procedure"),
                           bool(shutdown.get("monitor_may_already_be_active", False)))
    raise ValueError(f"no session backend adapter for emulator family: {family!r}")
