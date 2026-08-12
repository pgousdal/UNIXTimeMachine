import copy
import hashlib
import os
import sys
import tempfile
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

    def test_unpinned_hash_reports_hash_without_claiming_pass(self):
        directory = self.root / "media" / "unix-v7-pdp11"; directory.mkdir(parents=True)
        (directory / "v7.tap").write_bytes(b"synthetic")
        result = utmlib.verify_media("unix-v7-pdp11", self.root)[0]
        self.assertEqual(result.status, "UNPINNED")
        self.assertIn(hashlib.sha256(b"synthetic").hexdigest(), result.detail)

    def test_hash_match_and_mismatch(self):
        directory = self.root / "media" / "unix-v7-pdp11"; directory.mkdir(parents=True)
        (directory / "v7.tap").write_bytes(b"synthetic")
        manifest = self.manifest(); item = manifest["media"]["items"][0]
        item["sha256"] = hashlib.sha256(b"synthetic").hexdigest()
        with mock.patch.object(utmlib, "system_manifest", return_value=(Path("system.yml"), manifest)):
            self.assertEqual(utmlib.verify_media("unix-v7-pdp11", self.root)[0].status, "PASS")
            item["sha256"] = "0" * 64
            self.assertEqual(utmlib.verify_media("unix-v7-pdp11", self.root)[0].status, "FAIL")

    def test_session_copy_and_refusal_to_overwrite_preserve_golden(self):
        golden = self.root / "golden" / "unix-v7-pdp11" / "v7-rp06.dsk"
        golden.parent.mkdir(parents=True); golden.write_bytes(b"golden-data"); golden.chmod(0o440)
        before = utmlib.sha256(golden)
        workspace, _ = utmlib.prepare_session("unix-v7-pdp11", "test-session", self.root)
        (workspace / "rp0.dsk").write_bytes(b"changed session")
        self.assertEqual(utmlib.sha256(golden), before)
        with self.assertRaisesRegex(utmlib.UTMError, "overwrite"):
            utmlib.prepare_session("unix-v7-pdp11", "test-session", self.root)

    def test_golden_import_refuses_media_source_and_overwrite(self):
        media = self.root / "media" / "prepared.dsk"; media.parent.mkdir(); media.write_bytes(b"x")
        with self.assertRaisesRegex(utmlib.UTMError, "source media"):
            utmlib.import_golden("unix-v7-pdp11", media, self.root)
        source = self.root / "staging.dsk"; source.write_bytes(b"prepared")
        utmlib.import_golden("unix-v7-pdp11", source, self.root)
        with self.assertRaisesRegex(utmlib.UTMError, "overwrite"):
            utmlib.import_golden("unix-v7-pdp11", source, self.root)

    def test_unsafe_ids(self):
        for value in ("../escape", "/absolute", "UPPER", "a/b"):
            with self.assertRaises((utmlib.UTMError, ValueError)):
                utmlib.prepare_session(value, "safe", self.root)

    def test_runtime_generation(self):
        golden = self.root / "golden" / "unix-v7-pdp11" / "v7-rp06.dsk"
        golden.parent.mkdir(parents=True); golden.write_bytes(b"disk")
        utmlib.prepare_session("unix-v7-pdp11", "runtime-test", self.root)
        config = utmlib.render_runtime("unix-v7-pdp11", "runtime-test", self.root)
        text = config.read_text()
        self.assertIn("set cpu 11/70", text); self.assertIn("set rp0 rp06", text)
        self.assertIn(str(self.root / "sessions" / "unix-v7-pdp11" / "runtime-test" / "rp0.dsk"), text)
        self.assertNotIn("@SESSION_DISK@", text)

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

    def test_bounded_readiness(self):
        start = time.monotonic()
        status, _ = utmlib.readiness(self.root / "absent.log", ["login:"], 0.03, poll=0.005)
        self.assertEqual(status, "HUMAN_REQUIRED")
        self.assertLess(time.monotonic() - start, 0.5)
        log = self.root / "console.log"; log.write_text("\nlogin:")
        self.assertEqual(utmlib.readiness(log, ["login:"], 1)[0], "PASS")


if __name__ == "__main__":
    unittest.main()
