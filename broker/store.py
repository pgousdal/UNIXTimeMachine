from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

from .models import SessionRecord, SessionState, TRANSITIONS
from .session import InvalidTransition


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.directory = root / "state" / "broker"
        self.sessions = self.directory / "sessions"
        self.audit_path = root / "logs" / "broker-audit.jsonl"

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        lock = self.directory / "lock"
        with lock.open("a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def path(self, session_id: str) -> Path:
        return self.sessions / f"{session_id}.json"

    def load(self, session_id: str) -> SessionRecord:
        return SessionRecord.from_dict(json.loads(self.path(session_id).read_text(encoding="utf-8")))

    def all(self, strict: bool = True) -> list[SessionRecord]:
        if not self.sessions.is_dir():
            return []
        records = []
        for path in sorted(self.sessions.glob("*.json")):
            try:
                records.append(SessionRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, TypeError) as exc:
                if strict:
                    raise ValueError(f"invalid broker state file preserved: {path}: {exc}") from exc
        return records

    def save(self, record: SessionRecord) -> None:
        from scripts.utmlib import atomic_json
        record.updated_at = utc_now()
        if not record.created_at:
            record.created_at = record.updated_at
        atomic_json(self.path(record.session_id), record.as_dict())

    def transition(self, record: SessionRecord, state: SessionState, event: str,
                   detail: dict | None = None) -> None:
        old = SessionState(record.state)
        if state not in TRANSITIONS[old]:
            raise InvalidTransition(f"invalid session transition: {old.value} -> {state.value}")
        record.state = state.value
        self.save(record)
        self.audit(event, record, {"from": old.value, "to": state.value, **(detail or {})})

    def audit(self, event: str, record: SessionRecord | None = None,
              detail: dict | None = None) -> None:
        entry = {"event": event, "timestamp": utc_now()}
        if record is not None:
            entry.update({"session_id": record.session_id, "system_id": record.system_id,
                          "state": record.state})
        if detail:
            entry["detail"] = detail
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode()
        fd = os.open(self.audit_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
