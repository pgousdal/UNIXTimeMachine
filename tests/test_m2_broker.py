import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from broker.backend import Backend, PreparedSession
from broker.config import BrokerConfig
from broker.manager import Broker
from broker.models import SessionState
from broker.process import process_start_ticks
from broker.session import InvalidTransition, Session
from broker.store import Store
from scripts.utmlib import UTMError, atomic_json, sha256


CLEAN_EMULATOR = (
    "import os,tty\n"
    "tty.setraw(0); os.write(1,b'login:')\n"
    "data=b''\n"
    "while b'quit' not in data:\n"
    " data += os.read(0,1024)\n"
)
SILENT_EMULATOR = "import time; time.sleep(30)"
STUBBORN_EMULATOR = (
    "import os,signal,time,tty; tty.setraw(0); signal.signal(signal.SIGHUP,signal.SIG_IGN); "
    "os.write(1,b'login:'); time.sleep(30)"
)


class FakeBackend(Backend):
    def __init__(self, command=CLEAN_EMULATOR, patterns=None):
        self.code = command; self.patterns = patterns or ["login:"]

    def prepare(self, system_id, session_id, root):
        workspace = root / "sessions" / system_id / session_id
        workspace.mkdir(parents=True)
        golden = root / "golden" / system_id
        hashes = {}
        for disk_id, name in (("root", "rp0.dsk"), ("usr", "rp1.dsk")):
            target = workspace / name
            target.write_bytes((golden / name).read_bytes())
            hashes[disk_id] = sha256(golden / name)
        return PreparedSession(workspace, [sys.executable, "-c", self.code], self.patterns,
                               ["full-copy", "full-copy"], hashes)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        golden = self.root / "golden/unix-v7-pdp11"; golden.mkdir(parents=True)
        (golden / "rp0.dsk").write_bytes(b"immutable-root")
        (golden / "rp1.dsk").write_bytes(b"immutable-usr")
        self.golden_before = {p.name: sha256(p) for p in golden.iterdir()}
        self.write_config()

    def tearDown(self):
        # Ensure no synthetic supervisor/emulator survives a failed assertion.
        store = Store(self.root)
        for record in store.all(strict=False):
            for pid in (record.supervisor_pid, record.emulator_pid):
                if process_start_ticks(pid) is not None:
                    try: os.kill(pid, 9)
                    except ProcessLookupError: pass
        self.temp.cleanup()

    def write_config(self, **overrides):
        values = BrokerConfig(startup_timeout=1, readiness_timeout=2, idle_timeout=5,
                              absolute_timeout=10, shutdown_timeout=.3).as_dict()
        values.update(overrides)
        atomic_json(self.root / "state/broker-config.json", values)

    def request(self, backend=None, session_id=None):
        with mock.patch("broker.manager.backend_for", return_value=backend or FakeBackend()):
            return Broker(self.root).request("unix-v7-pdp11", session_id)

    def wait_state(self, session_id, states, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            record = Broker(self.root).get(session_id)
            if record.state in states: return record
            time.sleep(.02)
        self.fail(f"session did not reach {states}: {record.state}")

    def test_valid_and_invalid_state_transitions(self):
        session = Session("s", "system")
        session.transition(SessionState.ALLOCATED)
        session.transition(SessionState.PREPARING)
        with self.assertRaises(InvalidTransition): session.transition(SessionState.ACTIVE)

    def test_admission_limits_and_duplicate_refusal(self):
        self.write_config(max_total_sessions=3, max_sessions_per_system=1)
        first = self.request(session_id="fixed-session")
        with self.assertRaisesRegex(UTMError, "concurrent limit"):
            self.request(session_id="second-session")
        Broker(self.root).stop(first.session_id); Broker(self.root).release(first.session_id)
        with self.assertRaisesRegex(UTMError, "duplicate"):
            self.request(session_id="fixed-session")

        self.write_config(max_total_sessions=1, max_sessions_per_system=2)
        total = self.request(session_id="total-limit")
        with self.assertRaisesRegex(UTMError, "maximum total"):
            self.request(session_id="total-refused")
        Broker(self.root).stop(total.session_id)

    def test_deterministic_ids_are_monotonic_and_never_reused(self):
        first = self.request(); Broker(self.root).stop(first.session_id); Broker(self.root).release(first.session_id)
        second = self.request()
        self.assertEqual(first.session_id, "unix-v7-pdp11-000001")
        self.assertEqual(second.session_id, "unix-v7-pdp11-000002")

    def test_readiness_attach_detach_ctrl_e_and_clean_teardown(self):
        record = self.request(); record = self.wait_state(record.session_id, {"ready"})
        input_read, input_write = os.pipe(); output_read, output_write = os.pipe()
        os.write(input_write, b"\x05\x1d")
        Broker(self.root).attach(record.session_id, input_read, output_write)
        os.close(input_read); os.close(input_write); os.close(output_write)
        output = os.read(output_read, 4096); os.close(output_read)
        self.assertIn(b"Ctrl-E is passed", output)
        self.wait_state(record.session_id, {"ready"})
        stopped = Broker(self.root).stop(record.session_id)
        self.assertIn(stopped.state, {"resetting", "released"})
        if stopped.state == "resetting":
            stopped = self.wait_state(record.session_id, {"released"})
        released = Broker(self.root).release(record.session_id)
        self.assertEqual(released.state, "released")
        self.assertFalse(Path(record.workspace).exists())
        self.assertTrue(Path(record.transcript).is_file())
        golden = self.root / "golden/unix-v7-pdp11"
        self.assertEqual({p.name: sha256(p) for p in golden.iterdir()}, self.golden_before)
        events = {json.loads(line)["event"] for line in
                  (self.root / "logs/broker-audit.jsonl").read_text().splitlines()}
        self.assertTrue({"attach", "detach", "stop", "reset", "release"}.issubset(events))

    def test_readiness_timeout_is_bounded_and_audited(self):
        self.write_config(readiness_timeout=.15, shutdown_timeout=.3)
        started = time.monotonic(); record = self.request(FakeBackend(SILENT_EMULATOR))
        final = self.wait_state(record.session_id, {"failed", "resetting", "released"}, timeout=2)
        self.assertLess(time.monotonic() - started, 2)
        audit = (self.root / "logs/broker-audit.jsonl").read_text()
        self.assertIn('"kind":"readiness"', audit)
        self.assertIn(final.state, {"failed", "resetting", "released"})

    def test_idle_and_absolute_timeouts(self):
        for kind, settings in (("idle", {"idle_timeout": .15, "absolute_timeout": 3}),
                               ("absolute", {"idle_timeout": 3, "absolute_timeout": .15})):
            with self.subTest(kind=kind):
                self.write_config(readiness_timeout=2, shutdown_timeout=.3, **settings)
                record = self.request(session_id=f"timeout-{kind}")
                self.wait_state(record.session_id, {"failed", "resetting", "released"}, timeout=2)
        audit = (self.root / "logs/broker-audit.jsonl").read_text()
        self.assertIn('"kind":"idle"', audit); self.assertIn('"kind":"absolute"', audit)

    def test_failed_teardown_preserves_evidence(self):
        self.write_config(shutdown_timeout=.1)
        record = self.request(FakeBackend(STUBBORN_EMULATOR)); self.wait_state(record.session_id, {"ready"})
        failed = Broker(self.root).stop(record.session_id)
        self.assertEqual(failed.state, "failed")
        self.assertTrue(Path(record.workspace).is_dir())
        with self.assertRaisesRegex(UTMError, "still be running"):
            Broker(self.root).release(record.session_id)

    def test_stale_pid_and_reconciliation_are_conservative(self):
        store = Store(self.root)
        with store.locked():
            record = __import__("broker.models", fromlist=["SessionRecord"]).SessionRecord(
                session_id="stale-session", system_id="unix-v7-pdp11", state="starting",
                supervisor_pid=999999, supervisor_start_ticks=1,
                workspace=str(self.root / "sessions/unix-v7-pdp11/stale-session"))
            Path(record.workspace).mkdir(parents=True)
            store.save(record)
        result = Broker(self.root).reconcile()
        self.assertIn(("stale-session", "failed-preserved"), result)
        self.assertEqual(Broker(self.root).get("stale-session").state, "failed")
        self.assertTrue(Path(record.workspace).exists())

    def test_invalid_state_file_is_preserved_and_blocks_normal_admission(self):
        path = self.root / "state/broker/sessions/corrupt.json"
        path.parent.mkdir(parents=True); path.write_text("{not-json")
        with self.assertRaisesRegex(ValueError, "invalid broker state file preserved"):
            Broker(self.root).list()
        result = Broker(self.root).reconcile()
        self.assertIn((str(path), "invalid-state-preserved"), result)
        self.assertTrue(path.exists())

    def test_backend_abstraction_and_structured_audit_without_console(self):
        self.assertIsInstance(FakeBackend(), Backend)
        record = self.request(); self.wait_state(record.session_id, {"ready"})
        lines = [json.loads(line) for line in (self.root / "logs/broker-audit.jsonl").read_text().splitlines()]
        events = {line["event"] for line in lines}
        self.assertTrue({"request", "allocation", "preparation", "emulator_start",
                         "readiness_result"}.issubset(events))
        self.assertNotIn("login:", (self.root / "logs/broker-audit.jsonl").read_text())

    def test_startup_timeout_is_bounded(self):
        broker = Broker(self.root)
        with mock.patch("broker.manager.backend_for", return_value=FakeBackend()), \
             mock.patch("broker.manager.subprocess.Popen") as popen:
            popen.return_value.poll.return_value = None
            popen.return_value.terminate.return_value = None
            with self.assertRaisesRegex(UTMError, "startup exceeded"):
                broker.request("unix-v7-pdp11", "bounded-start")
        self.assertIn('"kind":"startup"', (self.root / "logs/broker-audit.jsonl").read_text())


if __name__ == "__main__":
    unittest.main()
