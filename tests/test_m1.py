import copy
import hashlib
import os
import sys
import tempfile
import threading
import time
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import utmlib
import utm as utm_cli
from manifestlib import system_manifest


class M1Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self):
        return copy.deepcopy(system_manifest("unix-v7-pdp11")[1])

    def test_missing_media(self):
        self.assertEqual(utmlib.verify_media("unix-v7-pdp11", self.root)[0].status, "MISSING")

    def test_canonical_media_identity_is_pinned(self):
        item = self.manifest()["media"]["items"][0]
        self.assertEqual(item["size"], 11711508)
        self.assertEqual(item["sha256"], "e2a6c5d420e2db62e992a95fce420bf311c3afa89b38381b8d212c92eef5a6cf")
        self.assertEqual(item["sha1"], "8056d35a2cb6529330f26db5754e858c9eab0462")

    def test_noncanonical_media_fails_without_authenticity_claim(self):
        directory = self.root / "media" / "unix-v7-pdp11"; directory.mkdir(parents=True)
        (directory / "v7.tap").write_bytes(b"synthetic")
        result = utmlib.verify_media("unix-v7-pdp11", self.root)[0]
        self.assertEqual(result.status, "FAIL")
        self.assertIn("expected 11711508", result.detail)

    def test_hash_match_and_mismatch(self):
        directory = self.root / "media" / "unix-v7-pdp11"; directory.mkdir(parents=True)
        (directory / "v7.tap").write_bytes(b"synthetic")
        manifest = self.manifest(); item = manifest["media"]["items"][0]
        item["size"] = len(b"synthetic")
        item["sha256"] = hashlib.sha256(b"synthetic").hexdigest()
        with mock.patch.object(utmlib, "system_manifest", return_value=(Path("system.yml"), manifest)):
            self.assertEqual(utmlib.verify_media("unix-v7-pdp11", self.root)[0].status, "PASS")
            item["sha256"] = "0" * 64
            self.assertEqual(utmlib.verify_media("unix-v7-pdp11", self.root)[0].status, "FAIL")

    def test_session_copy_and_refusal_to_overwrite_preserve_golden(self):
        golden_dir = self.root / "golden" / "unix-v7-pdp11"
        golden_dir.mkdir(parents=True)
        for name in ("rp0.dsk", "rp1.dsk"):
            (golden_dir / name).write_bytes(("golden-" + name).encode()); (golden_dir / name).chmod(0o440)
        before = {name: utmlib.sha256(golden_dir / name) for name in ("rp0.dsk", "rp1.dsk")}
        workspace, _ = utmlib.prepare_session("unix-v7-pdp11", "test-session", self.root)
        (workspace / "rp0.dsk").write_bytes(b"changed session")
        self.assertTrue((workspace / "rp1.dsk").is_file())
        self.assertEqual({name: utmlib.sha256(golden_dir / name) for name in before}, before)
        with self.assertRaisesRegex(utmlib.UTMError, "overwrite"):
            utmlib.prepare_session("unix-v7-pdp11", "test-session", self.root)

    def test_golden_import_refuses_media_source_and_overwrite(self):
        media = self.root / "media" / "prepared.dsk"; media.parent.mkdir(); media.write_bytes(b"x")
        with self.assertRaisesRegex(utmlib.UTMError, "source media"):
            utmlib.import_golden("unix-v7-pdp11", media, self.root)
        source = self.root / "staging"; source.mkdir()
        (source / "rp0.dsk").write_bytes(b"root")
        with self.assertRaisesRegex(utmlib.UTMError, "incomplete"):
            utmlib.import_golden("unix-v7-pdp11", source, self.root)
        (source / "rp1.dsk").write_bytes(b"usr")
        ownership = []
        with mock.patch.object(utmlib, "golden_group_id", return_value=4242), \
             mock.patch.object(utmlib.os, "chown",
                               side_effect=lambda path, uid, gid: ownership.append((Path(path), uid, gid))):
            utmlib.import_golden("unix-v7-pdp11", source, self.root)
        golden_dir = self.root / "golden" / "unix-v7-pdp11"
        self.assertEqual(golden_dir.stat().st_mode & 0o777, 0o750)
        for name in ("rp0.dsk", "rp1.dsk", "metadata.json"):
            mode = (golden_dir / name).stat().st_mode & 0o777
            self.assertEqual(mode, 0o440)
            self.assertEqual(mode & 0o007, 0, "golden members must not be world-accessible")
            self.assertNotEqual(mode & 0o040, 0, "enrolled operators need group read access")
            self.assertEqual(mode & 0o222, 0, "golden members must be immutable to operators")
        published = {path.name: (uid, gid) for path, uid, gid in ownership}
        transaction_dirs = [(path, uid, gid) for path, uid, gid in ownership
                            if path.name.startswith(".unix-v7-pdp11.import-")]
        self.assertEqual(len(transaction_dirs), 1)
        self.assertEqual(transaction_dirs[0][1:], (0, 4242))
        self.assertEqual(published["rp0.dsk"], (0, 4242))
        self.assertEqual(published["rp1.dsk"], (0, 4242))
        self.assertEqual(published["metadata.json"], (0, 4242))
        metadata = __import__("json").loads((golden_dir / "metadata.json").read_text())
        self.assertEqual(set(metadata["disks"]), {"root", "usr"})
        with self.assertRaisesRegex(utmlib.UTMError, "overwrite"):
            utmlib.import_golden("unix-v7-pdp11", source, self.root)

    def test_unreadable_golden_has_controlled_error_and_no_partial_session(self):
        golden = self.root / "golden" / "unix-v7-pdp11"
        golden.mkdir(parents=True)
        (golden / "rp0.dsk").write_bytes(b"root")
        (golden / "rp1.dsk").write_bytes(b"usr")
        denied = PermissionError(13, "Permission denied", str(golden / "rp0.dsk"))
        with mock.patch.object(utmlib, "sha256", side_effect=denied), \
             self.assertRaisesRegex(utmlib.UTMError, "root:unix-time-machine.*group enrollment"):
            utmlib.prepare_session("unix-v7-pdp11", "qualification-1", self.root)
        self.assertFalse((self.root / "sessions/unix-v7-pdp11/qualification-1").exists())

    def test_unsafe_ids(self):
        for value in ("../escape", "/absolute", "UPPER", "a/b"):
            with self.assertRaises((utmlib.UTMError, ValueError)):
                utmlib.prepare_session(value, "safe", self.root)

    def test_runtime_generation(self):
        golden = self.root / "golden" / "unix-v7-pdp11"
        golden.mkdir(parents=True)
        (golden / "rp0.dsk").write_bytes(b"root")
        (golden / "rp1.dsk").write_bytes(b"usr")
        utmlib.prepare_session("unix-v7-pdp11", "runtime-test", self.root)
        config = utmlib.render_runtime("unix-v7-pdp11", "runtime-test", self.root)
        text = config.read_text()
        self.assertIn("set cpu 11/70", text); self.assertIn("set cpu 2M", text)
        self.assertIn("set rp0 rp06", text); self.assertIn("set rp1 rp06", text)
        self.assertIn("set tm disabled", text)
        self.assertIn("set xq disabled", text); self.assertIn("set xu disabled", text)
        self.assertIn(str(self.root / "sessions" / "unix-v7-pdp11" / "runtime-test" / "rp0.dsk"), text)
        self.assertIn(str(self.root / "sessions" / "unix-v7-pdp11" / "runtime-test" / "rp1.dsk"), text)
        self.assertNotIn("set console log", text)
        self.assertNotIn("@SESSION_RP", text)
        self.assertNotIn(str(golden), text)

    def test_partial_session_set_is_rejected(self):
        workspace = self.root / "sessions" / "unix-v7-pdp11" / "partial"
        workspace.mkdir(parents=True); (workspace / "rp0.dsk").write_bytes(b"root")
        with self.assertRaisesRegex(utmlib.UTMError, "incomplete session"):
            utmlib.render_runtime("unix-v7-pdp11", "partial", self.root)

    def test_failed_session_copy_is_not_published(self):
        golden = self.root / "golden" / "unix-v7-pdp11"; golden.mkdir(parents=True)
        (golden / "rp0.dsk").write_bytes(b"root"); (golden / "rp1.dsk").write_bytes(b"usr")
        real_copy = utmlib.copy_exclusive
        calls = 0
        def fail_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic copy failure")
            return real_copy(source, destination)
        with mock.patch.object(utmlib, "copy_exclusive", side_effect=fail_second), self.assertRaises(OSError):
            utmlib.prepare_session("unix-v7-pdp11", "failed", self.root)
        parent = self.root / "sessions" / "unix-v7-pdp11"
        self.assertFalse((parent / "failed").exists())
        self.assertEqual(list(parent.glob(".failed.prepare-*")), [])

    def test_install_staging_has_explicit_bootstrap_and_runtime_phases(self):
        media = self.root / "media" / "unix-v7-pdp11"; media.mkdir(parents=True)
        tape = media / "v7.tap"; tape.write_bytes(b"synthetic")
        manifest = self.manifest(); item = manifest["media"]["items"][0]
        item["size"] = tape.stat().st_size; item["sha256"] = utmlib.sha256(tape)
        with mock.patch.object(utmlib, "system_manifest", return_value=(ROOT / "systems/unix-v7-pdp11/system.yml", manifest)):
            bootstrap, runtime = utmlib.prepare_install(
                "unix-v7-pdp11", self.root / "staging", self.root)
        self.assertEqual(bootstrap.name, "install-bootstrap.ini")
        self.assertEqual(runtime.name, "install-runtime.ini")
        bootstrap_text = bootstrap.read_text()
        runtime_text = runtime.read_text()
        self.assertIn("set cpu 11/45", bootstrap_text)
        self.assertIn("set cpu 256K", bootstrap_text)
        self.assertNotIn("set cpu 11/70", bootstrap_text)
        self.assertIn("set cpu 11/70", runtime_text)
        self.assertIn("set cpu 2M", runtime_text)
        self.assertNotIn("set cpu 11/45", runtime_text)
        for text in (bootstrap_text, runtime_text):
            self.assertIn("set rp0 rp06", text); self.assertIn("set rp1 rp06", text)
            self.assertIn(str(self.root / "staging/rp0.dsk"), text)
            self.assertIn(str(self.root / "staging/rp1.dsk"), text)
            self.assertIn("set xq disabled", text); self.assertIn("set xu disabled", text)
            self.assertNotIn("@", text)
        self.assertIn("attach -r tm0", bootstrap_text)
        self.assertIn(str(tape), bootstrap_text)
        self.assertIn("set tm disabled", runtime_text)
        self.assertNotIn("attach -r tm0", runtime_text)
        self.assertIn("V7 hpuboot is silent: type boot and Return", runtime_text)
        self.assertIn("type hp(0,0)unix and Return", runtime_text)
        self.assertFalse((self.root / "media/unix-v7-pdp11/rp0.dsk").exists())
        for protected in (self.root / "media/staging", self.root / "golden/staging"):
            with self.assertRaisesRegex(utmlib.UTMError, "outside"):
                utmlib.prepare_install("unix-v7-pdp11", protected, self.root)

    def test_missing_simh_executable(self):
        manifest = self.manifest()
        manifest["emulator"]["executable"] = str(self.root / "missing-pdp11")
        with self.assertRaisesRegex(utmlib.UTMError, "missing or non-executable SIMH"):
            utmlib.find_emulator(manifest)

    def test_simh_uses_only_canonical_absolute_executable(self):
        emulator = self.root / "pdp11"
        emulator.write_text("#!/bin/sh\nexit 0\n")
        emulator.chmod(0o755)
        manifest = self.manifest()
        manifest["emulator"]["executable"] = str(emulator)
        with mock.patch.dict(os.environ, {"PATH": str(self.root)}):
            self.assertEqual(utmlib.find_emulator(manifest), str(emulator))
        manifest["emulator"]["executable"] = "pdp11"
        with self.assertRaisesRegex(utmlib.UTMError, "absolute"):
            utmlib.find_emulator(manifest)

    def test_doctor_runs_canonical_simh_and_reports_success(self):
        emulator = self.root / "canonical-pdp11"
        emulator.write_text("#!/bin/sh\necho 'PDP-11 simulator V3.12-3'\n")
        emulator.chmod(0o755)
        output = StringIO()
        with mock.patch.object(utm_cli, "find_emulator", return_value=str(emulator)):
            with redirect_stdout(output):
                # Missing host directories still make the overall clean-host check fail.
                self.assertEqual(utm_cli.cmd_doctor(Namespace(root=str(self.root))), 1)
        self.assertIn(f"PASS    SIMH executable {emulator} is runnable", output.getvalue())

    def test_doctor_reports_missing_canonical_simh(self):
        output = StringIO()
        error = utmlib.UTMError("missing or non-executable SIMH executable: /canonical/pdp11")
        with mock.patch.object(utm_cli, "find_emulator", side_effect=error):
            with redirect_stdout(output):
                self.assertEqual(utm_cli.cmd_doctor(Namespace(root=str(self.root))), 1)
        self.assertIn("FAIL    missing or non-executable SIMH executable", output.getvalue())

    def test_doctor_controls_permission_error_and_is_read_only(self):
        output = StringIO()
        real_stat = Path.stat
        denied = self.root / "media"
        def selective_stat(path, *args, **kwargs):
            if path == denied:
                raise PermissionError(13, "Permission denied", str(path))
            return real_stat(path, *args, **kwargs)
        with mock.patch.object(Path, "stat", selective_stat), \
             mock.patch.object(utm_cli, "find_emulator", side_effect=utmlib.UTMError("missing")), \
             redirect_stdout(output):
            self.assertEqual(utm_cli.cmd_doctor(Namespace(root=str(self.root))), 1)
        self.assertIn(f"FAIL    directory {denied}: permission denied", output.getvalue())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bounded_readiness(self):
        start = time.monotonic()
        status, _ = utmlib.readiness(self.root / "absent.log", ["login:"], 0.03, poll=0.005)
        self.assertEqual(status, "HUMAN_REQUIRED")
        self.assertLess(time.monotonic() - start, 0.5)
        log = self.root / "console.log"; log.write_text("\nlogin:")
        self.assertEqual(utmlib.readiness(log, ["login:"], 1)[0], "PASS")

    def test_live_console_output_is_captured_before_process_exit(self):
        emulator = self.root / "live-console"
        emulator.write_text("#!/bin/sh\nprintf 'mem = 2020544\\r\\nlogin:'\nsleep 0.3\n")
        emulator.chmod(0o755)
        transcript = self.root / "console.log"
        output = self.root / "operator.out"
        input_read, input_write = os.pipe()
        started = threading.Event()
        result = []
        with output.open("wb", buffering=0) as operator:
            thread = threading.Thread(
                target=lambda: result.append(utmlib.interactive_console(
                    [str(emulator)], transcript, on_start=lambda _pid: started.set(),
                    stdin_fd=input_read, stdout_fd=operator.fileno())))
            thread.start()
            self.assertTrue(started.wait(1))
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and (not transcript.is_file() or
                                                     "login:" not in transcript.read_text(errors="replace")):
                time.sleep(0.01)
            self.assertIn("login:", transcript.read_text(errors="replace"))
            self.assertTrue(thread.is_alive(), "capture must be visible while SIMH is still running")
            self.assertEqual(utmlib.readiness(transcript, ["login:"], 0.2)[0], "PASS")
            thread.join(2)
        os.close(input_read)
        os.close(input_write)
        self.assertFalse(thread.is_alive(), "console relay must terminate with the emulator")
        self.assertEqual(result, [0])
        self.assertIn(b"login:", output.read_bytes())

    def test_foreground_console_input_and_output_are_preserved(self):
        emulator = self.root / "interactive-console"
        emulator.write_text(
            "#!/usr/bin/env python3\n"
            "import os, tty\n"
            "tty.setraw(0)\n"
            "os.write(1, b'ready>')\n"
            "data = os.read(0, 1)\n"
            "os.write(1, b'guest-read:' + data)\n")
        emulator.chmod(0o755)
        input_read, input_write = os.pipe()
        output = self.root / "operator.out"
        transcript = self.root / "console.log"
        with output.open("wb", buffering=0) as operator:
            thread = threading.Thread(target=utmlib.interactive_console, kwargs={
                "command": [str(emulator)], "log_path": transcript,
                "stdin_fd": input_read, "stdout_fd": operator.fileno()})
            thread.start()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and b"ready>" not in output.read_bytes():
                time.sleep(0.01)
            os.write(input_write, b"X")
            thread.join(2)
        os.close(input_read)
        os.close(input_write)
        self.assertFalse(thread.is_alive(), "foreground interaction must not hang")
        self.assertIn(b"guest-read:X", output.read_bytes())
        self.assertIn(b"guest-read:X", transcript.read_bytes())


if __name__ == "__main__":
    unittest.main()
