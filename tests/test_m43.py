import copy
import os
import tempfile
import unittest
import sys
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import utm, utmlib
from scripts.manifestlib import system_manifest


SYSTEM = "amix-a3000"


class M43RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.session = self.root / "sessions" / SYSTEM / "synthetic"
        self.session.mkdir(parents=True)
        (self.session / "amix-system.hdf").write_bytes(b"synthetic session disk")
        self.media = self.root / "media" / SYSTEM
        self.media.mkdir(parents=True)
        (self.media / "operator-rom").write_bytes(b"AMIROMTYPE1synthetic-rom")
        (self.media / "operator-rom-key").write_bytes(b"synthetic-key")

    def tearDown(self):
        self.temp.cleanup()

    def render(self):
        return utmlib.render_runtime(SYSTEM, "synthetic", self.root).read_text()

    def test_manifest_selects_canonical_runtime_configuration(self):
        manifest = system_manifest(SYSTEM)[1]
        self.assertEqual(manifest["emulator"]["configuration"], "runtime.fs-uae.in")
        self.assertEqual(manifest["emulator"]["rendered_configuration"], "runtime.fs-uae")

    def test_rendered_hardware_and_writable_session_rdb(self):
        text = self.render()
        for option in (
            "amiga_model = A3000", "cpu = 68030", "mmu = 68030", "fpu = 68882",
            "chip_memory = 2048", "motherboard_ram = 16384", "jit_compiler = 0",
            "network_card = 0", "bsdsocket_library = 0", "hard_drive_0_type = rdb",
            "hard_drive_0_controller = scsi6", "hard_drive_0_read_only = 0",
        ):
            self.assertIn(option, text)
        self.assertIn(f"hard_drive_0 = {self.session / 'amix-system.hdf'}", text)
        self.assertNotIn(str(self.root / "golden"), text)
        self.assertNotIn("synthetic session disk", text)
        self.assertNotIn("synthetic-rom", text)
        self.assertNotIn("synthetic-key", text)
        self.assertNotIn("@", text)

    def test_missing_session_and_disk_fail_cleanly(self):
        with self.assertRaisesRegex(utmlib.UTMError, "session does not exist"):
            utmlib.render_runtime(SYSTEM, "absent", self.root)
        (self.session / "amix-system.hdf").unlink()
        with self.assertRaisesRegex(utmlib.UTMError, "incomplete session disk set"):
            self.render()

    def test_missing_rom_and_required_key_fail_cleanly(self):
        (self.media / "operator-rom").unlink()
        with self.assertRaisesRegex(utmlib.UTMError, "compatible-a3000-kickstart-rom"):
            self.render()
        (self.media / "operator-rom").write_bytes(b"AMIROMTYPE1synthetic-rom")
        (self.media / "operator-rom-key").unlink()
        with self.assertRaisesRegex(utmlib.UTMError, "rom-key.*required"):
            self.render()

    def test_unencrypted_rom_does_not_require_key(self):
        (self.media / "operator-rom").write_bytes(b"synthetic-unencrypted-rom")
        (self.media / "operator-rom-key").unlink()
        text = self.render()
        self.assertNotIn("kickstart_key_file", text)

    def test_missing_configuration_is_controlled(self):
        manifest = copy.deepcopy(system_manifest(SYSTEM)[1])
        manifest["emulator"].pop("configuration")
        with mock.patch.object(utmlib, "system_manifest", return_value=(
                ROOT / "systems/amix-a3000/system.yml", manifest)):
            with self.assertRaisesRegex(utmlib.UTMError, "missing required emulator.configuration"):
                self.render()

    def test_system_start_uses_existing_safe_argv_supervisor(self):
        fake = self.root / "fs-uae"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        manifest = copy.deepcopy(system_manifest(SYSTEM)[1])
        manifest["emulator"]["executable"] = str(fake)
        args = Namespace(root=str(self.root), system_id=SYSTEM, session_id="synthetic")
        captured = []

        def supervisor(command, _log, on_start):
            captured.append(command)
            on_start(424242)
            return 0

        with mock.patch.object(utm, "system_manifest", return_value=(Path("system.yml"), manifest)), \
             mock.patch.object(utmlib, "system_manifest", return_value=(
                 ROOT / "systems/amix-a3000/system.yml", manifest)), \
             mock.patch.object(utm, "interactive_console", side_effect=supervisor), \
             mock.patch.object(utm, "pid_alive", return_value=False):
            self.assertEqual(utm.cmd_system_start(args), 0)
        self.assertEqual(captured, [[str(fake), str(self.session / "runtime.fs-uae")]])
        self.assertIsInstance(captured[0], list)

    def test_ready_is_truthfully_human_required(self):
        args = Namespace(root=str(self.root), system_id=SYSTEM, session_id="synthetic", timeout=0)
        self.assertEqual(utm.cmd_system_ready(args), 1)


if __name__ == "__main__":
    unittest.main()
