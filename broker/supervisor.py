from __future__ import annotations

import argparse
import errno
import json
import os
import pty
import selectors
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from .config import BrokerConfig
from .models import SessionState
from .process import process_start_ticks
from .store import Store, utc_now


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
        socket_path = Path(record.socket_path)
        socket_path.unlink(missing_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path)); os.chmod(socket_path, 0o660); listener.listen(1)
        listener.setblocking(False)
        master, slave = pty.openpty()
        transcript_path = Path(record.transcript)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript = transcript_path.open("ab", buffering=0)
        process = subprocess.Popen(spec["command"], stdin=slave, stdout=slave, stderr=slave,
                                   start_new_session=True, close_fds=True)
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
        try:
            while True:
                now = time.monotonic()
                elapsed = now - self.started
                if not self.failed and not self.ready and elapsed >= self.config.readiness_timeout and not self.stop_requested:
                    self.store.audit("readiness_result", self.store.load(self.session_id), {"result": "timeout"})
                    self.store.audit("timeout", self.store.load(self.session_id), {"kind": "readiness"})
                    self.stop_requested = True; self.stop_reason = "readiness-timeout"
                if not self.failed and elapsed >= self.config.absolute_timeout and not self.stop_requested:
                    self.store.audit("timeout", self.store.load(self.session_id), {"kind": "absolute"})
                    self.stop_requested = True; self.stop_reason = "absolute-timeout"
                if not self.failed and now - self.last_activity >= self.config.idle_timeout and not self.stop_requested:
                    self.store.audit("timeout", self.store.load(self.session_id), {"kind": "idle"})
                    self.stop_requested = True; self.stop_reason = "idle-timeout"
                if self.stop_requested and shutdown_deadline is None:
                    current = self.store.load(self.session_id)
                    if current.state in {SessionState.STARTING.value, SessionState.READY.value,
                                         SessionState.ACTIVE.value, SessionState.FAILED.value}:
                        self.transition(SessionState.STOPPING, "stop", {"reason": self.stop_reason})
                    os.write(master, bytes.fromhex(spec["shutdown_hex"]))
                    shutdown_deadline = now + self.config.shutdown_timeout
                if shutdown_deadline is not None and now >= shutdown_deadline and process.poll() is None:
                    reason = "safe shutdown unconfirmed; process left running for inspection"
                    self.store.audit("timeout", self.store.load(self.session_id), {"kind": "shutdown"})
                    self.update(failure=reason, stop_reason=self.stop_reason)
                    self.transition(SessionState.FAILED, "failure", {
                        "reason": reason})
                    # Retain the PTY/socket and supervisor so an operator can inspect,
                    # attach, clean up the guest, and retry a bounded stop.
                    self.failed = True; self.stop_requested = False; shutdown_deadline = None
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
                            self.update(attached_at=utc_now(), last_activity_at=utc_now())
                    elif key.data == "console":
                        try: data = os.read(master, 65536)
                        except OSError as exc:
                            if exc.errno == errno.EIO: data = b""
                            else: raise
                        if data:
                            transcript.write(data); tail = (tail + data)[-16384:]
                            self.last_activity = now; self.update(last_activity_at=utc_now())
                            if self.attached is not None:
                                try: self.attached.sendall(data)
                                except OSError: self.detach(selector)
                            if not self.ready and any(pattern.encode() in tail for pattern in spec["patterns"]):
                                self.ready = True; self.transition(SessionState.READY, "readiness_result", {"result": "pass"})
                                self.update(ready_at=utc_now())
                        else:
                            try: selector.unregister(master)
                            except Exception: pass
                    else:
                        try: data = self.attached.recv(65536)
                        except OSError: data = b""
                        if not data or b"\x1d" in data:
                            before = data.split(b"\x1d", 1)[0]
                            if before: os.write(master, before)
                            self.detach(selector)
                        else:
                            os.write(master, data); self.last_activity = now
                            self.update(last_activity_at=utc_now())
                code = process.poll()
                if code is not None:
                    record = self.update(exit_code=code, stop_reason=self.stop_reason)
                    if record.state == SessionState.STOPPING.value:
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
