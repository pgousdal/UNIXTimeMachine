from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import pty
import selectors
import signal
import socket
import subprocess
import sys
import termios
import time
from pathlib import Path

from .config import BrokerConfig
from .models import SessionState
from .process import process_start_ticks
from .store import Store, utc_now
from .shutdown import shutdown_driver


def configure_controlling_terminal() -> None:
    """Complete the session setup after Popen's setsid(), before exec()."""
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.tcsetpgrp(0, os.getpgrp())


class Supervisor:
    def __init__(self, root: Path, session_id: str):
        self.root = root
        self.session_id = session_id
        self.store = Store(root)
        self.config = BrokerConfig.load(root)
        self.stop_requested = False
        self.stop_reason = None
        self.attached = None
        self.last_activity = time.monotonic()
        self.started = time.monotonic()
        self.ready = False
        self.failed = False
        self.readiness_deadline = None
        self.control_log_path = None

    def control_log(self, event: str) -> None:
        if self.control_log_path is None:
            return
        with self.control_log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"{utc_now()} {event}\n")

    def update(self, **changes):
        with self.store.locked():
            record = self.store.load(self.session_id)
            for key, value in changes.items():
                setattr(record, key, value)
            self.store.save(record)
            return record

    def transition(self, state: SessionState, event: str, detail=None):
        with self.store.locked():
            record = self.store.load(self.session_id)
            if record.state == state.value:
                return record
            self.store.transition(record, state, event, detail)
            return record

    def request_stop(self, signum, _frame):
        self.stop_requested = True
        self.stop_reason = "operator" if signum == signal.SIGTERM else "supervisor-signal"

    def run(self) -> int:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        record = self.update(supervisor_pid=os.getpid(),
                             supervisor_start_ticks=process_start_ticks(os.getpid()))
        spec = json.loads((Path(record.workspace) / "broker-launch.json").read_text())
        console = spec.get("console", {"kind": "stdio-pty"})
        if console.get("kind") != "stdio-pty":
            raise RuntimeError(f"unsupported console transport: {console.get('kind')!r}")
        shutdown = spec["shutdown"]
        stop_driver = shutdown_driver(shutdown)
        socket_path = Path(record.socket_path)
        socket_path.unlink(missing_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path)); os.chmod(socket_path, 0o660); listener.listen(1)
        listener.setblocking(False)
        master, slave = pty.openpty()
        transcript_path = Path(record.transcript)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        self.control_log_path = transcript_path.parent / "supervisor.log"
        transcript = transcript_path.open("ab", buffering=0)
        process = subprocess.Popen(spec["command"], stdin=slave, stdout=slave, stderr=slave,
                                   start_new_session=True, close_fds=True,
                                   preexec_fn=configure_controlling_terminal)
        os.close(slave)
        os.set_blocking(master, False)
        self.transition(SessionState.STARTING, "emulator_start",
                        {"pid": process.pid, "socket": str(socket_path)})
        self.update(emulator_pid=process.pid, emulator_start_ticks=process_start_ticks(process.pid),
                    last_activity_at=utc_now())
        selector = selectors.DefaultSelector()
        selector.register(listener, selectors.EVENT_READ, "listener")
        selector.register(master, selectors.EVENT_READ, "console")
        tail = b""
        shutdown_deadline = None
        shutdown_phase = None
        try:
            while True:
                now = time.monotonic()
                if self.stop_requested and shutdown_deadline is None:
                    current = self.store.load(self.session_id)
                    if current.state in {SessionState.STARTING.value, SessionState.READY.value,
                                         SessionState.ACTIVE.value, SessionState.FAILED.value}:
                        self.transition(SessionState.STOPPING, "stop", {"reason": self.stop_reason})
                    try:
                        request = json.loads((Path(record.workspace) / "broker-stop.json").read_text())
                    except (OSError, ValueError):
                        request = {}
                    self.control_log("stop request accepted")
                    if request.get("guest_synced"):
                        self.control_log("guest-sync attestation present")
                    shutdown_phase = stop_driver.begin(
                        lambda data: os.write(master, data), self.control_log)
                    shutdown_deadline = now + self.config.shutdown_timeout
                if shutdown_deadline is not None and now >= shutdown_deadline and process.poll() is None:
                    if shutdown_phase == "monitor":
                        self.control_log("monitor prompt not observed")
                        reason = stop_driver.timeout_reason(shutdown_phase)
                    else:
                        reason = stop_driver.timeout_reason(shutdown_phase)
                    self.control_log("shutdown timeout/failure")
                    self.store.audit("timeout", self.store.load(self.session_id), {"kind": "shutdown"})
                    self.update(failure=reason, stop_reason=self.stop_reason)
                    self.transition(SessionState.FAILED, "failure", {
                        "reason": reason})
                    # Retain the PTY/socket and supervisor so an operator can inspect,
                    # attach, clean up the guest, and retry a bounded stop.
                    self.failed = True; self.stop_requested = False; shutdown_deadline = None
                    shutdown_phase = None
                for key, _ in selector.select(0.1):
                    if key.data == "listener":
                        conn, _ = listener.accept(); conn.setblocking(False)
                        if self.attached is not None:
                            conn.sendall(b"session already attached\r\n"); conn.close()
                        else:
                            self.attached = conn; selector.register(conn, selectors.EVENT_READ, "client")
                            self.last_activity = now
                            state = self.store.load(self.session_id).state
                            if state == SessionState.READY.value:
                                self.transition(SessionState.ACTIVE, "attach")
                            else:
                                self.store.audit("attach", self.store.load(self.session_id))
                            changes = {"attached_at": utc_now(), "last_activity_at": utc_now()}
                            if state == SessionState.STARTING.value and self.readiness_deadline is None:
                                changes["readiness_started_at"] = utc_now()
                                self.readiness_deadline = now + self.config.readiness_timeout
                                self.store.audit("readiness_begin", self.store.load(self.session_id),
                                                 {"trigger": "first-attach"})
                            self.update(**changes)
                    elif key.data == "console":
                        try: data = os.read(master, 65536)
                        except OSError as exc:
                            if exc.errno == errno.EIO: data = b""
                            else: raise
                        if data:
                            transcript.write(data); tail = (tail + data)[-16384:]
                            prior_phase = shutdown_phase
                            shutdown_phase = stop_driver.observe(
                                data, self.ready, shutdown_phase,
                                lambda payload: os.write(master, payload), self.control_log)
                            if prior_phase == "monitor" and shutdown_phase == "exit":
                                shutdown_deadline = now + self.config.shutdown_timeout
                            self.last_activity = now; self.update(last_activity_at=utc_now())
                            if self.attached is not None:
                                try: self.attached.sendall(data)
                                except OSError: self.detach(selector)
                            if not self.ready and any(pattern.encode() in tail for pattern in spec["patterns"]):
                                self.ready = True
                                self.transition(SessionState.READY, "readiness_result", {"result": "pass"})
                                self.update(ready_at=utc_now())
                                if self.attached is not None:
                                    self.transition(SessionState.ACTIVE, "activate",
                                                    {"reason": "ready-while-attached"})
                        else:
                            try: selector.unregister(master)
                            except Exception: pass
                    else:
                        try: data = self.attached.recv(65536)
                        except OSError: data = b""
                        if not data or b"\x1d" in data:
                            before = data.split(b"\x1d", 1)[0]
                            if before:
                                os.write(master, before)
                                stop_driver.invalidate_on_input()
                            self.detach(selector)
                        else:
                            os.write(master, data)
                            # Input invalidates backend-owned live prompt evidence.
                            stop_driver.invalidate_on_input()
                            self.last_activity = now
                            self.update(last_activity_at=utc_now())
                # Consume all console events selected at the boundary before deciding that
                # readiness lost the race. Also drain bytes that became readable after the
                # selector snapshot, so a marker already emitted at the boundary wins.
                now = time.monotonic()
                elapsed = now - self.started
                if (not self.ready and self.readiness_deadline is not None
                        and now >= self.readiness_deadline):
                    try: boundary_data = os.read(master, 65536)
                    except BlockingIOError: boundary_data = b""
                    except OSError as exc:
                        if exc.errno == errno.EIO: boundary_data = b""
                        else: raise
                    if boundary_data:
                        transcript.write(boundary_data)
                        tail = (tail + boundary_data)[-16384:]
                        self.last_activity = now; self.update(last_activity_at=utc_now())
                        if self.attached is not None:
                            try: self.attached.sendall(boundary_data)
                            except OSError: self.detach(selector)
                        if any(pattern.encode() in tail for pattern in spec["patterns"]):
                            self.ready = True
                            self.transition(SessionState.READY, "readiness_result", {"result": "pass"})
                            self.update(ready_at=utc_now())
                            if self.attached is not None:
                                self.transition(SessionState.ACTIVE, "activate",
                                                {"reason": "ready-while-attached"})
                timeout_kind = None
                if (not self.failed and not self.ready and self.readiness_deadline is not None
                        and now >= self.readiness_deadline and not self.stop_requested):
                    self.store.audit("readiness_result", self.store.load(self.session_id),
                                     {"result": "timeout"})
                    timeout_kind = "readiness"
                elif not self.failed and elapsed >= self.config.absolute_timeout and not self.stop_requested:
                    timeout_kind = "absolute"
                elif (not self.failed and now - self.last_activity >= self.config.idle_timeout
                      and not self.stop_requested):
                    timeout_kind = "idle"
                if timeout_kind is not None:
                    self.store.audit("timeout", self.store.load(self.session_id), {"kind": timeout_kind})
                    reason = f"{timeout_kind} timeout; emulator and workspace preserved for inspection"
                    self.update(failure=reason, stop_reason=f"{timeout_kind}-timeout")
                    self.transition(SessionState.FAILED, "failure", {"reason": reason})
                    # Automatic expiry cannot assert that a historical guest was synced.
                    # Preserve it without injecting monitor or guest-console commands.
                    self.failed = True
                code = process.poll()
                if code is not None:
                    if shutdown_phase == "exit":
                        self.control_log("emulator exit observed")
                    record = self.update(exit_code=code, stop_reason=self.stop_reason)
                    if record.state == SessionState.STOPPING.value:
                        if shutdown_phase != "exit":
                            self.control_log("monitor prompt not observed")
                            self.control_log("shutdown timeout/failure")
                            reason = "emulator exited before confirmed shutdown; workspace preserved"
                            self.update(failure=reason)
                            self.transition(SessionState.FAILED, "failure",
                                            {"reason": reason, "exit_code": code})
                            return 2
                        self.transition(SessionState.RESETTING, "reset", {"exit_code": code})
                        return 0
                    if record.state == SessionState.FAILED.value:
                        self.transition(SessionState.RESETTING, "reset",
                                      {"exit_code": code, "after_failure": True})
                        return 0
                    self.update(failure=f"emulator exited unexpectedly ({code})")
                    self.transition(SessionState.FAILED, "failure", {"reason": "emulator exited", "exit_code": code})
                    return 2
        finally:
            if self.attached is not None: self.attached.close()
            selector.close(); listener.close(); transcript.close(); os.close(master)
            socket_path.unlink(missing_ok=True)

    def detach(self, selector):
        if self.attached is None: return
        try: selector.unregister(self.attached)
        except Exception: pass
        self.attached.close(); self.attached = None
        record = self.store.load(self.session_id)
        self.store.audit("detach", record)
        if record.state == SessionState.ACTIVE.value:
            self.transition(SessionState.READY, "detach")
        self.update(attached_at=None, last_activity_at=utc_now())


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True); parser.add_argument("--session-id", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root)
    result = Supervisor(root, args.session_id).run()
    if result == 0:
        # A confirmed emulator exit makes reset/discard deterministic; diagnostics live in logs/state.
        from .manager import Broker
        Broker(root).release(args.session_id)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
