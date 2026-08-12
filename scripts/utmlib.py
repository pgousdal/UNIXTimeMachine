"""Preservation-safe operator primitives for UNIX Time Machine."""
from __future__ import annotations

import grp
import hashlib
import json
import os
import pty
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path

# Script and package imports must share the same UTMError class so the CLI can
# reliably catch errors raised by broker modules.
if __name__ == "utmlib":
    sys.modules.setdefault("scripts.utmlib", sys.modules[__name__])
else:
    sys.modules.setdefault("utmlib", sys.modules[__name__])

try:
    from manifestlib import system_manifest
except ModuleNotFoundError:  # Package import used by the broker supervisor.
    from .manifestlib import system_manifest

DEFAULT_ROOT = Path("/srv/unix-time-machine")
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
GOLDEN_GROUP = "unix-time-machine"


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


def prepared_disks(manifest: dict) -> list[dict]:
    disks = manifest.get("prepared", {}).get("disks")
    if not isinstance(disks, list) or not disks:
        raise UTMError("manifest has no prepared disk set")
    return disks


def golden_group_id() -> int:
    try:
        return grp.getgrnam(GOLDEN_GROUP).gr_gid
    except KeyError as exc:
        raise UTMError(f"required golden-data group does not exist: {GOLDEN_GROUP}") from exc


def set_golden_access(path: Path, mode: int, group_id: int) -> None:
    os.chown(path, 0, group_id)
    path.chmod(mode)


def import_golden(system_id: str, source: Path, host_root: Path) -> tuple[Path, list[str]]:
    _, manifest = system_manifest(safe_id(system_id, "system id"))
    source = source.resolve(strict=True)
    media_root = (host_root / "media").resolve()
    if source == media_root or media_root in source.parents:
        raise UTMError("refusing to treat source media as a prepared golden disk")
    if not source.is_dir():
        raise UTMError("golden import source must be a staging directory containing the complete disk set")
    disks = prepared_disks(manifest)
    sources = [(disk, source / disk["golden_filename"]) for disk in disks]
    missing = [str(path) for _, path in sources if not path.is_file()]
    if missing:
        raise UTMError("incomplete staging disk set; missing: " + ", ".join(missing))
    golden_root = host_root / "golden"
    golden_root.mkdir(parents=True, exist_ok=True)
    destination = golden_root / system_id
    if destination.exists() and any(destination.iterdir()):
        raise UTMError(f"refusing to overwrite existing golden set: {destination}")
    transaction = golden_root / f".{system_id}.import-{os.getpid()}"
    if transaction.exists():
        raise UTMError(f"stale golden import transaction exists: {transaction}")
    transaction.mkdir(mode=0o750)
    methods = []
    hashes = {}
    try:
        group_id = golden_group_id()
        set_golden_access(transaction, 0o750, group_id)
        for disk, disk_source in sources:
            target = transaction / disk["golden_filename"]
            methods.append(copy_exclusive(disk_source, target))
            set_golden_access(target, 0o440, group_id)
            hashes[disk["id"]] = {"filename": disk["golden_filename"], "sha256": sha256(target)}
        atomic_json(transaction / "metadata.json", {
            "disks": hashes, "source_path": str(source), "system_id": system_id
        })
        set_golden_access(transaction / "metadata.json", 0o440, group_id)
        if destination.exists():
            destination.rmdir()  # only an empty provisioning-era directory is removable
        os.replace(transaction, destination)
    except Exception:
        shutil.rmtree(transaction, ignore_errors=True)
        raise
    return destination, methods


def prepare_session(system_id: str, session_id: str, host_root: Path) -> tuple[Path, list[str]]:
    _, manifest = system_manifest(safe_id(system_id, "system id"))
    safe_id(session_id, "session id")
    disks = prepared_disks(manifest)
    golden_dir = host_root / "golden" / system_id
    goldens = [(disk, golden_dir / disk["golden_filename"]) for disk in disks]
    try:
        missing = [str(path) for _, path in goldens
                   if not stat.S_ISREG(path.stat().st_mode)]
    except FileNotFoundError:
        missing = [str(path) for _, path in goldens if not path.is_file()]
    except PermissionError as exc:
        raise UTMError(
            f"golden disk set is not accessible; verify root:{GOLDEN_GROUP} ownership, "
            "0750 directory mode, 0440 file modes, and operator group enrollment"
        ) from exc
    if missing:
        raise UTMError("incomplete golden disk set; missing: " + ", ".join(missing))
    try:
        before = {disk["id"]: sha256(path) for disk, path in goldens}
    except PermissionError as exc:
        raise UTMError(
            f"golden disk set is not readable; verify root:{GOLDEN_GROUP} ownership, "
            "0750 directory mode, 0440 file modes, and operator group enrollment"
        ) from exc
    workspace = host_root / "sessions" / system_id / session_id
    if workspace.exists():
        raise UTMError(f"refusing to overwrite existing session: {workspace}")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    transaction = workspace.parent / f".{session_id}.prepare-{os.getpid()}"
    if transaction.exists():
        raise UTMError(f"stale session preparation transaction exists: {transaction}")
    transaction.mkdir(mode=0o750)
    try:
        methods = []
        try:
            for disk, golden in goldens:
                destination = transaction / disk["session_filename"]
                methods.append(copy_exclusive(golden, destination))
                destination.chmod(0o640)
            after = {disk["id"]: sha256(path) for disk, path in goldens}
        except PermissionError as exc:
            raise UTMError(
                f"golden disk set became unreadable; verify root:{GOLDEN_GROUP} ownership, "
                "0750 directory mode, 0440 file modes, and operator group enrollment"
            ) from exc
        if before != after:
            raise UTMError("preservation invariant violated: golden disk set changed during copy")
        atomic_json(transaction / "session.json", {
            "copy_methods": methods, "golden_sha256": before, "session_id": session_id,
            "state": "prepared", "system_id": system_id
        })
        os.replace(transaction, workspace)
    except Exception:
        shutil.rmtree(transaction, ignore_errors=True)
        raise
    return workspace, methods


def render_runtime(system_id: str, session_id: str, host_root: Path) -> Path:
    manifest_path, manifest = system_manifest(safe_id(system_id, "system id"))
    safe_id(session_id, "session id")
    workspace = host_root / "sessions" / system_id / session_id
    disks = prepared_disks(manifest)
    template = manifest_path.parent / manifest["emulator"]["configuration"]
    config = template.read_text(encoding="utf-8")
    replacements = {}
    for disk in disks:
        path = workspace / disk["session_filename"]
        if not path.is_file():
            raise UTMError(f"incomplete session disk set; missing: {path}")
        replacements[disk["runtime_token"]] = str(path.resolve())
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


def prepare_install(system_id: str, staging: Path, host_root: Path) -> tuple[Path, Path]:
    manifest_path, manifest = system_manifest(safe_id(system_id, "system id"))
    staging = staging.resolve()
    for protected in ((host_root / "media").resolve(), (host_root / "golden").resolve()):
        if staging == protected or protected in staging.parents:
            raise UTMError("installation staging must be outside media/ and golden/")
    if staging.exists():
        raise UTMError(f"refusing to overwrite existing staging directory: {staging}")
    media_results = verify_media(system_id, host_root)
    if any(result.status != "PASS" for result in media_results):
        raise UTMError("canonical installation media must pass verification before staging")
    media = manifest["media"]
    item = media["items"][0]
    media_dir = host_root / "media" / media.get("directory", system_id)
    tape = next(path for path in (media_dir / name for name in item["filenames"]) if path.is_file())
    staging.mkdir(parents=True, mode=0o750)
    try:
        emulator = manifest["emulator"]
        templates = (
            (emulator["installation_bootstrap_configuration"], "install-bootstrap.ini"),
            (emulator["installation_runtime_configuration"], "install-runtime.ini"),
        )
        replacements = {
            "@INSTALL_TAPE@": str(tape.resolve()),
            "@INSTALL_BOOTSTRAP_CONSOLE_LOG@": str((staging / "install-bootstrap-console.log").resolve()),
            "@INSTALL_RUNTIME_CONSOLE_LOG@": str((staging / "install-runtime-console.log").resolve()),
        }
        for disk in prepared_disks(manifest):
            replacements[f"@STAGING_{disk['unit']}@"] = str((staging / disk["golden_filename"]).resolve())
        for value in replacements.values():
            if any(char in value for char in "\n\r\t ;\""):
                raise UTMError(f"installation path contains characters unsafe for SIMH: {value}")
        outputs = []
        for template_name, output_name in templates:
            config = (manifest_path.parent / template_name).read_text(encoding="utf-8")
            for token, value in replacements.items():
                config = config.replace(token, value)
            if "@" in config:
                raise UTMError("unresolved token in SIMH installation configuration")
            output = staging / output_name
            output.write_text(config, encoding="utf-8")
            outputs.append(output)
        return outputs[0], outputs[1]
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def find_emulator(manifest: dict) -> str:
    configured = manifest["emulator"].get("executable")
    if not configured or not Path(configured).is_absolute():
        raise UTMError("SIMH manifest must select an absolute executable path")
    path = Path(configured)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise UTMError(f"missing or non-executable SIMH executable: {path}")
    return str(path)


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


def interactive_console(command: list[str], log_path: Path, on_start=None,
                        stdin_fd: int = 0, stdout_fd: int = 1) -> int:
    """Run a local console on a PTY and tee its live output to a transcript."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    pid, master_fd = pty.fork()
    if pid == 0:
        try:
            os.execv(command[0], command)
        except BaseException as exc:
            os.write(2, f"unable to execute {command[0]}: {exc}\n".encode())
            os._exit(127)

    selector = selectors.DefaultSelector()
    selector.register(master_fd, selectors.EVENT_READ, "console")
    try:
        selector.register(stdin_fd, selectors.EVENT_READ, "input")
    except (OSError, PermissionError):
        pass
    saved_terminal = termios.tcgetattr(stdin_fd) if os.isatty(stdin_fd) else None
    if saved_terminal is not None:
        tty.setraw(stdin_fd)
    status = None
    console_open = True
    try:
        if on_start is not None:
            on_start(pid)
        with log_path.open("wb", buffering=0) as transcript:
            while status is None or console_open:
                for key, _ in selector.select(0.1):
                    if key.data == "console":
                        try:
                            data = os.read(master_fd, 65536)
                        except OSError as exc:
                            # Linux PTY masters report EIO after the slave closes.
                            if exc.errno == 5:
                                data = b""
                            else:
                                raise
                        if not data:
                            selector.unregister(master_fd)
                            console_open = False
                        else:
                            transcript.write(data)
                            view = memoryview(data)
                            while view:
                                view = view[os.write(stdout_fd, view):]
                    else:
                        data = os.read(stdin_fd, 65536)
                        if not data:
                            selector.unregister(stdin_fd)
                        else:
                            view = memoryview(data)
                            while view:
                                view = view[os.write(master_fd, view):]
                if status is None:
                    waited, child_status = os.waitpid(pid, os.WNOHANG)
                    if waited == pid:
                        status = child_status
    except BaseException:
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        raise
    finally:
        if saved_terminal is not None:
            termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, saved_terminal)
        selector.close()
        os.close(master_fd)
    return os.waitstatus_to_exitcode(status)


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
