import tempfile
import unittest
import json
import os
import time
from pathlib import Path
from unittest import mock

import yaml

from broker.backend import Backend, PreparedSession, ShutdownProtocol, SimhBackend, backend_for
from broker.config import BrokerConfig
from broker.manager import Broker
from scripts.utmlib import (UTMError, import_golden, prepare_install,
                            atomic_json, prepare_session, render_runtime, sha256, verify_media)

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = "43bsd-vax"


class VaxFakeBackend(Backend):
    def prepare(self, system_id, session_id, root):
        workspace = root / "sessions" / system_id / session_id
        workspace.mkdir(parents=True)
        source = root / "golden" / system_id / "rq0.dsk"
        (workspace / "rq0.dsk").write_bytes(source.read_bytes())
        code = ("import os,tty\n"
                "tty.setraw(0); os.write(1,b'login:'); d=b''\n"
                "while b'\\x05' not in d: d += os.read(0,1024)\n"
                "os.write(1,b'\\r\\nsim>'); d=b''\n"
                "while b'quit\\r' not in d: d += os.read(0,1024)\n")
        import sys
        return PreparedSession(workspace, [sys.executable, "-c", code], ["login:"],
                               ["full-copy"], {"system": sha256(source)})

    def shutdown_protocol(self):
        return ShutdownProtocol(True, b"\x05", b"sim>", b"quit\r")


class HaltToMonitorBackend(VaxFakeBackend):
    def prepare(self, system_id, session_id, root):
        prepared = super().prepare(system_id, session_id, root)
        code = ("import os,tty\n"
                "tty.setraw(0); os.write(1,b'old transcript sim> text\\r\\nlogin:'); d=b''\n"
                "while b'shutdown\\r' not in d: d += os.read(0,1024)\n"
                "os.write(1,b'syncing disks... done\\r\\nHALT\\r\\nInfinite loop ...\\r\\nsim>'); d=b''\n"
                "while b'quit\\r' not in d:\n"
                " d += os.read(0,1024)\n"
                " if b'\\x05' in d: os.write(1,b'REDUNDANT_CONTROL_E')\n"
                "os.write(1,b'QUIT_RECEIVED')\n")
        import sys
        return PreparedSession(prepared.workspace, [sys.executable, "-c", code], ["login:"],
                               prepared.copy_methods, prepared.golden_sha256)

    def shutdown_protocol(self):
        return ShutdownProtocol(True, b"\x05", b"sim>", b"quit\r", None, True)


class M3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def supply_media(self):
        media = self.root / "media" / SYSTEM
        media.mkdir(parents=True)
        for name, data in (("43bsd-dist.tap", b"tape"),
                           ("43bsd-miniroot.dsk", b"mini"),
                           ("boot42", b"boot")):
            (media / name).write_bytes(data)
        return media

    def test_manifest_is_supported_vax780_profile(self):
        manifest = yaml.safe_load((ROOT / "systems/43bsd-vax/system.yml").read_text())
        self.assertEqual(manifest["id"], SYSTEM)
        self.assertEqual(manifest["machine"]["model"], "VAX-11/780")
        self.assertEqual(manifest["emulator"]["profile"], "vax780")
        self.assertEqual(manifest["prepared"]["disks"][0]["device"], "RA81")
        backend = backend_for(SYSTEM)
        self.assertIsInstance(backend, SimhBackend)
        self.assertIn("/etc/shutdown -h now", backend.shutdown_protocol().guest_procedure)
        self.assertTrue(backend.shutdown_protocol().monitor_may_already_be_active)

    def test_media_missing_unpinned_and_duplicate_mismatch(self):
        self.assertTrue(all(r.status == "MISSING" for r in verify_media(SYSTEM, self.root)))
        media = self.supply_media()
        self.assertTrue(all(r.status == "UNPINNED" for r in verify_media(SYSTEM, self.root)))
        (media / "43.tap").write_bytes(b"other")
        tape = next(r for r in verify_media(SYSTEM, self.root)
                    if r.logical_name == "simh-distribution-tape")
        self.assertEqual(tape.status, "FAIL")

    def test_install_requires_explicit_unpinned_boundary_and_renders_all_artifacts(self):
        media = self.supply_media()
        canonical = media / "43bsd-miniroot.dsk"
        canonical.chmod(0o440)
        source_hash = sha256(canonical)
        staging = self.root / "staging" / "fresh"
        with self.assertRaisesRegex(UTMError, "allow-unpinned"):
            prepare_install(SYSTEM, staging, self.root)
        bootstrap, runtime = prepare_install(SYSTEM, staging, self.root, allow_unpinned=True)
        for output in (bootstrap, runtime):
            text = output.read_text()
            self.assertNotIn("@", text)
            self.assertIn("set xu disabled", text)
        self.assertIn("attach rq1", bootstrap.read_text())
        self.assertIn("attach rq0", runtime.read_text())
        bootstrap_copy = staging / "bootstrap-miniroot.dsk"
        bootstrap_text = bootstrap.read_text()
        self.assertIn(f"attach rq0 {bootstrap_copy}", bootstrap_text)
        self.assertNotIn(f"attach rq0 {canonical}", bootstrap_text)
        self.assertTrue(os.access(bootstrap_copy, os.W_OK))
        self.assertEqual(bootstrap_copy.stat().st_mode & 0o777, 0o640)
        self.assertEqual(bootstrap_copy.stat().st_size, canonical.stat().st_size)
        self.assertEqual(sha256(canonical), source_hash)
        self.assertEqual(canonical.stat().st_mode & 0o777, 0o440)
        metadata = json.loads((staging / "install.json").read_text())
        provenance = metadata["bootstrap_copies"]["miniroot-disk"]
        self.assertIn(provenance["copy_method"], {"reflink", "full-copy"})
        self.assertEqual(provenance["source_path"], str(canonical))
        self.assertEqual(provenance["source_sha256"], source_hash)
        self.assertEqual(provenance["output_sha256"], sha256(bootstrap_copy))
        with self.assertRaisesRegex(UTMError, "overwrite"):
            prepare_install(SYSTEM, staging, self.root, allow_unpinned=True)

    def test_install_rejects_unsafe_or_protected_staging(self):
        self.supply_media()
        with self.assertRaisesRegex(UTMError, "outside media"):
            prepare_install(SYSTEM, self.root / "media/new", self.root, True)

    @mock.patch("scripts.utmlib.set_golden_access")
    @mock.patch("scripts.utmlib.golden_group_id", return_value=123)
    def test_complete_atomic_golden_and_disposable_session_preserve_hash(self, _gid, _access):
        staging = self.root / "staging"; staging.mkdir()
        (staging / "rq0.dsk").write_bytes(b"installed")
        destination, _ = import_golden(SYSTEM, staging, self.root)
        before = sha256(destination / "rq0.dsk")
        workspace, _ = prepare_session(SYSTEM, "vax-session", self.root)
        (workspace / "rq0.dsk").write_bytes(b"mutated session")
        self.assertEqual(sha256(destination / "rq0.dsk"), before)
        self.assertTrue((destination / "metadata.json").is_file())
        with self.assertRaisesRegex(UTMError, "overwrite"):
            import_golden(SYSTEM, staging, self.root)

    @mock.patch("scripts.utmlib.set_golden_access")
    @mock.patch("scripts.utmlib.golden_group_id", return_value=123)
    def test_golden_rejects_partial_set_and_never_imports_tape(self, _gid, _access):
        staging = self.root / "empty"; staging.mkdir()
        with self.assertRaisesRegex(UTMError, "incomplete"):
            import_golden(SYSTEM, staging, self.root)
        self.assertFalse((self.root / "golden" / SYSTEM).exists())

    @mock.patch("scripts.utmlib.set_golden_access")
    @mock.patch("scripts.utmlib.golden_group_id", return_value=123)
    def test_golden_import_ignores_bootstrap_scratch_and_contains_only_expected_disk(self,
                                                                                   _gid, _access):
        staging = self.root / "staging"; staging.mkdir()
        (staging / "rq0.dsk").write_bytes(b"installed")
        (staging / "bootstrap-miniroot.dsk").write_bytes(b"scratch")
        (staging / "install.json").write_text("{}")
        destination, _ = import_golden(SYSTEM, staging, self.root)
        self.assertEqual({path.name for path in destination.iterdir()},
                         {"rq0.dsk", "metadata.json"})

    def test_vax_runtime_is_session_local_and_networkless(self):
        self.supply_media()
        golden = self.root / "golden" / SYSTEM; golden.mkdir(parents=True)
        (golden / "rq0.dsk").write_bytes(b"gold")
        prepare_session(SYSTEM, "isolated", self.root)
        config = render_runtime(SYSTEM, "isolated", self.root).read_text()
        self.assertIn(str(self.root / "sessions" / SYSTEM / "isolated/rq0.dsk"), config)
        self.assertIn(str(self.root / "media" / SYSTEM / "boot42"), config)
        self.assertIn("set xu disabled", config)
        self.assertNotRegex(config.lower(), r"telnet|attach xu|attach xub")

    def test_pinned_vax_discovery_contract(self):
        manifest = yaml.safe_load((ROOT / "systems/43bsd-vax/system.yml").read_text())
        self.assertEqual(manifest["emulator"]["executable"],
                         "/opt/unix-time-machine/simh/v3.12-3/vax780")

    def test_broker_request_uses_vax_profile_and_releases_disposable_disk(self):
        golden = self.root / "golden" / SYSTEM; golden.mkdir(parents=True)
        (golden / "rq0.dsk").write_bytes(b"immutable-vax")
        before = sha256(golden / "rq0.dsk")
        atomic_json(self.root / "state/broker-config.json",
                    BrokerConfig(startup_timeout=1, readiness_timeout=1, idle_timeout=5,
                                 absolute_timeout=5, shutdown_timeout=.5).as_dict())
        with mock.patch("broker.manager.backend_for", return_value=VaxFakeBackend()):
            record = Broker(self.root).request(SYSTEM, "vax-broker")
        self.assertEqual(record.system_id, SYSTEM)
        Broker(self.root).stop(record.session_id, guest_synced=True)
        deadline = __import__("time").monotonic() + 2
        while Broker(self.root).get(record.session_id).state != "released":
            if __import__("time").monotonic() > deadline:
                self.fail("VAX broker session did not release")
            __import__("time").sleep(.02)
        self.assertFalse(Path(record.workspace).exists())
        self.assertEqual(sha256(golden / "rq0.dsk"), before)

    def test_guest_halt_monitor_is_consumed_without_redundant_control_e(self):
        golden = self.root / "golden" / SYSTEM; golden.mkdir(parents=True)
        (golden / "rq0.dsk").write_bytes(b"immutable-vax")
        before = sha256(golden / "rq0.dsk")
        atomic_json(self.root / "state/broker-config.json",
                    BrokerConfig(startup_timeout=1, readiness_timeout=1, idle_timeout=5,
                                 absolute_timeout=5, shutdown_timeout=.5).as_dict())
        with mock.patch("broker.manager.backend_for", return_value=HaltToMonitorBackend()):
            record = Broker(self.root).request(SYSTEM, "halt-to-monitor")
        deadline = time.monotonic() + 2
        while Broker(self.root).get(record.session_id).state != "ready":
            if time.monotonic() > deadline:
                self.fail("VAX fake did not become ready")
            time.sleep(.01)
        input_read, input_write = os.pipe(); output_read, output_write = os.pipe()
        os.write(input_write, b"shutdown\r\x1d"); os.close(input_write)
        Broker(self.root).attach(record.session_id, input_read, output_write)
        os.close(input_read); os.close(output_write); os.close(output_read)
        time.sleep(.1)
        Broker(self.root).stop(record.session_id, guest_synced=True)
        while Broker(self.root).get(record.session_id).state != "released":
            if time.monotonic() > deadline:
                self.fail("monitor-active VAX session did not release")
            time.sleep(.01)
        transcript = Path(record.transcript).read_bytes()
        self.assertIn(b"HALT", transcript)
        self.assertIn(b"QUIT_RECEIVED", transcript)
        self.assertNotIn(b"REDUNDANT_CONTROL_E", transcript)
        diagnostics = (Path(record.transcript).parent / "supervisor.log").read_text()
        fresh = diagnostics.index("fresh live monitor prompt observed")
        accepted = diagnostics.index("stop request accepted")
        quit_sent = diagnostics.index("quit sent")
        self.assertLess(fresh, accepted)
        self.assertLess(accepted, quit_sent)
        self.assertNotIn("Ctrl-E sent", diagnostics)
        self.assertEqual(sha256(golden / "rq0.dsk"), before)

    def test_historical_monitor_text_is_not_shutdown_evidence(self):
        golden = self.root / "golden" / SYSTEM; golden.mkdir(parents=True)
        (golden / "rq0.dsk").write_bytes(b"immutable-vax")
        atomic_json(self.root / "state/broker-config.json",
                    BrokerConfig(startup_timeout=1, readiness_timeout=1, idle_timeout=5,
                                 absolute_timeout=5, shutdown_timeout=.1).as_dict())
        with mock.patch("broker.manager.backend_for", return_value=HaltToMonitorBackend()):
            record = Broker(self.root).request(SYSTEM, "historical-prompt")
        deadline = time.monotonic() + 2
        while Broker(self.root).get(record.session_id).state != "ready":
            if time.monotonic() > deadline:
                self.fail("VAX fake did not become ready")
            time.sleep(.01)
        failed = Broker(self.root).stop(record.session_id, guest_synced=True)
        self.assertEqual(failed.state, "failed")
        diagnostics = (Path(record.transcript).parent / "supervisor.log").read_text()
        self.assertIn("Ctrl-E sent", diagnostics)
        self.assertNotIn("quit sent", diagnostics)
        self.assertTrue(Path(record.workspace).is_dir())


if __name__ == "__main__":
    unittest.main()
