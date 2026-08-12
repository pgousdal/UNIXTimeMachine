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


class Backend(ABC):
    @abstractmethod
    def prepare(self, system_id: str, session_id: str, root: Path) -> PreparedSession:
        raise NotImplementedError

    def safe_shutdown_bytes(self) -> bytes:
        return b"\x05quit\r"


class SimhBackend(Backend):
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
        return SimhBackend()
    raise ValueError(f"no session backend adapter for emulator family: {family!r}")
