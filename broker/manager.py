from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

from scripts.manifestlib import system_manifest
from scripts.utmlib import UTMError, atomic_json, safe_id, sha256

from .backend import backend_for
from .config import BrokerConfig
from .models import SessionRecord, SessionState
from .process import process_matches, process_start_ticks
from .store import Store, utc_now


# Failed sessions retain their slot until inspected and released: their emulator
# or mutable evidence may still exist, so excluding them would over-admit.
OCCUPYING = {state.value for state in SessionState if state != SessionState.RELEASED}


class Broker:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.store = Store(self.root)
        self.config = BrokerConfig.load(self.root)

    def _next_id(self, system_id: str) -> str:
        counter_path = self.store.directory / "counter.json"
        try: data = json.loads(counter_path.read_text(encoding="utf-8"))
        except FileNotFoundError: data = {"next": 1}
        number = int(data.get("next", 1))
        while True:
            candidate = f"{system_id}-{number:06d}"
            workspace = self.root / "sessions" / system_id / candidate
            if not self.store.path(candidate).exists() and not workspace.exists():
                atomic_json(counter_path, {"next": number + 1})
                return candidate
            number += 1

    def request(self, system_id: str, requested_id: str | None = None) -> SessionRecord:
        safe_id(system_id, "system id"); system_manifest(system_id); backend = backend_for(system_id)
        with self.store.locked():
            active = [r for r in self.store.all() if r.state in OCCUPYING]
            if len(active) >= self.config.max_total_sessions:
                raise UTMError("broker admission refused: maximum total concurrent sessions reached")
            per_system = sum(r.system_id == system_id for r in active)
            if per_system >= self.config.limit_for(system_id):
                raise UTMError(f"broker admission refused: concurrent limit reached for {system_id}")
            session_id = safe_id(requested_id, "session id") if requested_id else self._next_id(system_id)
            workspace = self.root / "sessions" / system_id / session_id
            if self.store.path(session_id).exists() or workspace.exists():
                raise UTMError(f"duplicate session refused: {session_id}")
            record = SessionRecord(session_id=session_id, system_id=system_id)
            self.store.save(record); self.store.audit("request", record)
            self.store.transition(record, SessionState.ALLOCATED, "allocation")
            self.store.transition(record, SessionState.PREPARING, "preparation")
        try:
            prepared = backend.prepare(system_id, session_id, self.root)
            socket_path = self.store.directory / f"{session_id}.sock"
            transcript = self.root / "logs" / "sessions" / session_id / "console.log"
            launch = {"command": prepared.command, "patterns": prepared.readiness_patterns,
                      "shutdown_hex": backend.safe_shutdown_bytes().hex()}
            atomic_json(prepared.workspace / "broker-launch.json", launch)
            with self.store.locked():
                record = self.store.load(session_id)
                record.workspace = str(prepared.workspace); record.socket_path = str(socket_path)
                record.transcript = str(transcript); record.copy_methods = prepared.copy_methods
                record.golden_sha256 = prepared.golden_sha256
                self.store.save(record)
            supervisor_log = transcript.parent / "supervisor.log"
            supervisor_log.parent.mkdir(parents=True, exist_ok=True)
            with supervisor_log.open("ab", buffering=0) as diagnostics:
                process = subprocess.Popen(
                    [sys.executable, "-m", "broker.supervisor", "--root", str(self.root),
                     "--session-id", session_id], cwd=str(Path(__file__).resolve().parents[1]),
                    stdin=subprocess.DEVNULL, stdout=diagnostics, stderr=diagnostics,
                    start_new_session=True)
            deadline = time.monotonic() + self.config.startup_timeout
            while time.monotonic() < deadline:
                time.sleep(0.02)
                current = self.store.load(session_id)
                if current.state in {SessionState.STARTING.value, SessionState.READY.value,
                                     SessionState.ACTIVE.value}:
                    # Ownership intentionally transfers to the persistent state record. Avoid
                    # Popen's misleading "still running" warning when this short CLI exits.
                    process.returncode = 0
                    return current
                if current.state == SessionState.FAILED.value:
                    raise UTMError(current.failure or "session supervisor failed during startup")
                if process.poll() is not None:
                    detail = supervisor_log.read_text(encoding="utf-8", errors="replace")[-2000:]
                    raise UTMError(f"session supervisor exited during startup ({process.returncode}): {detail}")
            self.store.audit("timeout", self.store.load(session_id), {"kind": "startup"})
            process.terminate()
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: pass
            raise UTMError(f"session startup exceeded bounded timeout ({self.config.startup_timeout}s)")
        except Exception as exc:
            with self.store.locked():
                record = self.store.load(session_id)
                if record.state not in {SessionState.FAILED.value, SessionState.RELEASED.value}:
                    record.failure = str(exc)
                    self.store.transition(record, SessionState.FAILED, "failure", {"reason": str(exc)})
            raise

    def get(self, session_id: str) -> SessionRecord:
        safe_id(session_id, "session id")
        try: return self.store.load(session_id)
        except FileNotFoundError as exc: raise UTMError(f"unknown session: {session_id}") from exc

    def list(self) -> list[SessionRecord]:
        return self.store.all()

    def stop(self, session_id: str) -> SessionRecord:
        record = self.get(session_id)
        if record.state in {SessionState.RESETTING.value, SessionState.RELEASED.value}:
            return record
        if not process_matches(record.supervisor_pid, record.supervisor_start_ticks):
            raise UTMError("session supervisor is not running; reconcile before teardown")
        os.kill(record.supervisor_pid, signal.SIGTERM)
        deadline = time.monotonic() + self.config.shutdown_timeout + 2
        while time.monotonic() < deadline:
            current = self.get(session_id)
            if current.state in {SessionState.RESETTING.value, SessionState.RELEASED.value,
                                 SessionState.FAILED.value}:
                return current
            time.sleep(0.05)
        self.store.audit("timeout", self.get(session_id), {"kind": "shutdown-wait"})
        raise UTMError("bounded shutdown wait expired; session preserved for inspection")

    def release(self, session_id: str) -> SessionRecord:
        with self.store.locked():
            record = self.get(session_id)
            if record.state == SessionState.RELEASED.value: return record
            if record.state == SessionState.FAILED.value:
                if process_matches(record.emulator_pid, record.emulator_start_ticks):
                    raise UTMError("failed emulator may still be running; evidence preserved")
                self.store.transition(record, SessionState.RESETTING, "reset",
                                      {"operator_release_after_failure": True})
            elif record.state != SessionState.RESETTING.value:
                raise UTMError("release requires a stopped/resetting session")
            _, manifest = system_manifest(record.system_id)
            try:
                actual = {disk["id"]: sha256(self.root / "golden" / record.system_id /
                                              disk["golden_filename"])
                          for disk in manifest["prepared"]["disks"]}
            except OSError as exc:
                record.failure = f"golden verification failed; workspace preserved: {exc}"
                self.store.transition(record, SessionState.FAILED, "failure",
                                      {"reason": record.failure})
                raise UTMError(record.failure) from exc
            if record.golden_sha256 and actual != record.golden_sha256:
                record.failure = "golden hash changed; workspace preserved"
                self.store.transition(record, SessionState.FAILED, "failure",
                                      {"reason": record.failure})
                raise UTMError(record.failure)
            workspace = Path(record.workspace) if record.workspace else None
            if workspace and workspace.exists():
                try:
                    shutil.rmtree(workspace)
                except OSError as exc:
                    record.failure = f"session reset failed; workspace preserved: {exc}"
                    self.store.transition(record, SessionState.FAILED, "failure",
                                          {"reason": record.failure})
                    raise UTMError(record.failure) from exc
            self.store.transition(record, SessionState.RELEASED, "release")
            return record

    def attach(self, session_id: str, stdin_fd=0, stdout_fd=1) -> None:
        record = self.get(session_id)
        if record.state not in {SessionState.STARTING.value, SessionState.READY.value,
                                SessionState.ACTIVE.value}:
            raise UTMError(f"session is not attachable in state {record.state}")
        if not record.socket_path:
            raise UTMError("local console unavailable: session has no console transport")
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try: client.connect(record.socket_path)
        except OSError as exc:
            client.close()
            raise UTMError("local console unavailable; supervisor socket is missing or inaccessible") from exc
        client.setblocking(False)
        selector = selectors.DefaultSelector(); selector.register(client, selectors.EVENT_READ, "socket")
        selector.register(stdin_fd, selectors.EVENT_READ, "input")
        saved = termios.tcgetattr(stdin_fd) if os.isatty(stdin_fd) else None
        if saved is not None: tty.setraw(stdin_fd)
        try:
            os.write(stdout_fd, b"Local attach; Ctrl-] detaches, Ctrl-E is passed to SIMH.\r\n")
            while True:
                for key, _ in selector.select(0.5):
                    if key.data == "socket":
                        data = client.recv(65536)
                        if not data: return
                        os.write(stdout_fd, data)
                    else:
                        data = os.read(stdin_fd, 65536)
                        if not data: return
                        client.sendall(data)
                        if b"\x1d" in data: return
        finally:
            if saved is not None: termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, saved)
            selector.close(); client.close()

    def reconcile(self) -> list[tuple[str, str]]:
        results = []
        with self.store.locked():
            if self.store.sessions.is_dir():
                for path in sorted(self.store.sessions.glob("*.json")):
                    try:
                        json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError) as exc:
                        self.store.audit("reconcile", None, {
                            "result": "invalid-state-preserved", "path": str(path),
                            "reason": str(exc)})
                        results.append((str(path), "invalid-state-preserved"))
            records = self.store.all(strict=False)
            for record in records:
                state = SessionState(record.state)
                if state in {SessionState.RELEASED, SessionState.FAILED, SessionState.RESETTING}:
                    results.append((record.session_id, "unchanged")); continue
                supervisor = process_matches(record.supervisor_pid, record.supervisor_start_ticks)
                emulator = process_matches(record.emulator_pid, record.emulator_start_ticks)
                if supervisor:
                    results.append((record.session_id, "healthy")); continue
                reason = "supervisor missing; emulator still running" if emulator else "stale session; no matching processes"
                record.failure = reason
                self.store.transition(record, SessionState.FAILED, "failure", {"reason": reason})
                self.store.audit("reconcile", record, {"result": "preserved", "reason": reason})
                results.append((record.session_id, "failed-preserved"))
            sessions_root = self.root / "sessions"
            if sessions_root.is_dir():
                known = {Path(r.workspace).resolve() for r in records if r.workspace}
                for transaction in sessions_root.glob("*/.*.prepare-*"):
                    if transaction.resolve() not in known:
                        self.store.audit("reconcile", None, {"result": "orphan-preserved", "path": str(transaction)})
                        results.append((str(transaction), "orphan-preserved"))
        return results
