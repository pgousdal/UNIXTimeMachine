"""Preservation-safe operator primitives for UNIX Time Machine."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from manifestlib import system_manifest

DEFAULT_ROOT = Path("/srv/unix-time-machine")
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class UTMError(RuntimeError):
    pass


def safe_id(value: str, label: str = "identifier") -> str:
    if not SAFE_NAME.fullmatch(value):
        raise UTMError(f"unsafe {label}: {value!r} (use lowercase letters, digits, and hyphens)")
    return value


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class MediaResult:
    logical_name: str
    status: str
    detail: str


def verify_media(system_id: str, host_root: Path) -> list[MediaResult]:
    _, manifest = system_manifest(safe_id(system_id, "system id"))
    media = manifest.get("media", {})
    directory = host_root / "media" / media.get("directory", system_id)
    results = []
    for item in media.get("items", []):
        logical = item["logical_name"]
        names = item.get("filenames", [])
        candidates = [directory / name for name in names]
        found = [path for path in candidates if path.is_file()]
        if not found:
            status = "MISSING" if item.get("required", True) else "PASS"
            results.append(MediaResult(logical, status, f"expected one of: {', '.join(names)}"))
            continue
        if len(found) > 1:
            results.append(MediaResult(logical, "FAIL", "multiple accepted filenames are present"))
            continue
        path = found[0]
        expected_size = item.get("size")
        if expected_size is not None and path.stat().st_size != expected_size:
            results.append(MediaResult(logical, "FAIL", f"size {path.stat().st_size}, expected {expected_size}"))
            continue
        expected_hash = item.get("sha256")
        actual_hash = sha256(path)
        if expected_hash is None:
            results.append(MediaResult(logical, "UNPINNED", f"{path.name} sha256={actual_hash}"))
        elif actual_hash.lower() == expected_hash.lower():
            results.append(MediaResult(logical, "PASS", f"{path.name} sha256 verified"))
        else:
            results.append(MediaResult(logical, "FAIL", f"{path.name} sha256={actual_hash}, expected {expected_hash}"))
    return results


def copy_exclusive(source: Path, destination: Path) -> str:
    source = source.resolve(strict=True)
    if not source.is_file():
        raise UTMError(f"source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise UTMError(f"refusing to overwrite existing file: {destination}")
    try:
        subprocess.run(["cp", "--reflink=always", "--", str(source), str(destination)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        method = "reflink"
    except (FileNotFoundError, subprocess.CalledProcessError):
        try:
            with source.open("rb") as src, destination.open("xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            shutil.copystat(source, destination)
            method = "full-copy"
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return method


def import_golden(system_id: str, source: Path, host_root: Path) -> tuple[Path, str]:
    _, manifest = system_manifest(safe_id(system_id, "system id"))
    source = source.resolve(strict=True)
    media_root = (host_root / "media").resolve()
    if source == media_root or media_root in source.parents:
        raise UTMError("refusing to treat source media as a prepared golden disk")
    destination = host_root / "golden" / system_id / manifest["prepared"]["golden_filename"]
    method = copy_exclusive(source, destination)
    destination.chmod(0o440)
    atomic_json(destination.parent / "metadata.json", {
        "golden_sha256": sha256(destination), "source_path": str(source), "system_id": system_id
    })
    return destination, method


def prepare_session(system_id: str, session_id: str, host_root: Path) -> tuple[Path, str]:
    _, manifest = system_manifest(safe_id(system_id, "system id"))
    safe_id(session_id, "session id")
    golden = host_root / "golden" / system_id / manifest["prepared"]["golden_filename"]
    if not golden.is_file():
        raise UTMError(f"missing prepared golden disk: {golden}")
    before = sha256(golden)
    workspace = host_root / "sessions" / system_id / session_id
    if workspace.exists():
        raise UTMError(f"refusing to overwrite existing session: {workspace}")
    workspace.mkdir(parents=True, mode=0o750)
    destination = workspace / manifest["prepared"]["session_filename"]
    try:
        method = copy_exclusive(golden, destination)
        destination.chmod(0o640)
        after = sha256(golden)
        if before != after:
            raise UTMError("preservation invariant violated: golden disk changed during copy")
        atomic_json(workspace / "session.json", {
            "copy_method": method, "golden_sha256": before, "session_id": session_id,
            "state": "prepared", "system_id": system_id
        })
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
    return workspace, method


def render_runtime(system_id: str, session_id: str, host_root: Path) -> Path:
    manifest_path, manifest = system_manifest(safe_id(system_id, "system id"))
    safe_id(session_id, "session id")
    workspace = host_root / "sessions" / system_id / session_id
    disk = workspace / manifest["prepared"]["session_filename"]
    if not disk.is_file():
        raise UTMError(f"missing session disk: {disk}")
    template = manifest_path.parent / manifest["emulator"]["configuration"]
    config = template.read_text(encoding="utf-8")
    replacements = {"@SESSION_DISK@": str(disk.resolve()), "@CONSOLE_LOG@": str((workspace / "console.log").resolve())}
    for token, value in replacements.items():
        if any(char in value for char in "\n\r\t ;\""):
            raise UTMError(f"runtime path contains characters unsafe for SIMH: {value}")
        config = config.replace(token, value)
    if "@" in config:
        raise UTMError("unresolved token in SIMH runtime configuration")
    output = workspace / "runtime.ini"
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_text(config, encoding="utf-8")
    os.replace(temporary, output)
    return output


def find_emulator(manifest: dict) -> str:
    for name in manifest["emulator"].get("executables", []):
        path = shutil.which(name)
        if path:
            return path
    raise UTMError(f"missing SIMH executable; tried: {', '.join(manifest['emulator'].get('executables', []))}")


def readiness(log_path: Path, patterns: list[str], timeout: float, poll: float = 0.2) -> tuple[str, str]:
    deadline = time.monotonic() + max(0, timeout)
    last = ""
    while True:
        if log_path.is_file():
            last = log_path.read_text(encoding="utf-8", errors="replace")[-8192:]
            if any(pattern in last for pattern in patterns):
                return "PASS", last
        if time.monotonic() >= deadline:
            return "HUMAN_REQUIRED", last
        time.sleep(min(poll, max(0, deadline - time.monotonic())))


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def stop_process(pid: int, timeout: float = 10) -> bool:
    os.kill(pid, signal.SIGINT)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.1)
    return False
