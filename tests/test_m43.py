import copy
import json
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
from scripts.amix_m42 import config_text
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
        (self.media / "amiga-os-310-a3000.rom").write_bytes(b"AMIROMTYPE1synthetic-rom")
        (self.media / "rom.key").write_bytes(b"synthetic-key")

    def tearDown(self):
        self.temp.cleanup()

    def render(self):
        return utmlib.render_runtime(SYSTEM, "synthetic", self.root).read_text()

    def stop_args(self, *, guest_synced=False, failed_boot=False,
                  session_id="synthetic"):
        return Namespace(root=str(self.root), system_id=SYSTEM,
                         session_id=session_id, timeout=0.25,
                         guest_synced=guest_synced, failed_boot=failed_boot)

    def write_running_state(self, pid=424242):
        state = self.root / "state" / f"{SYSTEM}.json"
        utmlib.atomic_json(state, {
            "config": str(self.session / "runtime.fs-uae"),
            "emulator": "/synthetic/fs-uae", "pid": pid,
            "session_id": "synthetic", "system_id": SYSTEM,
        })
        return state

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

    def test_runtime_exactly_matches_m42_first_boot_except_session_paths(self):
        rendered = self.render()
        known_good = config_text(
            self.media / "amiga-os-310-a3000.rom", self.media / "rom.key",
            Path("/tmp/proven-amix-session.hdf"), None, None, None,
            Path("/tmp/proven-amix-runtime-logs"))
        expected = known_good.replace(
            "/tmp/proven-amix-session.hdf", str(self.session / "amix-system.hdf")
        ).replace(
            "/tmp/proven-amix-runtime-logs", str(self.session / "fs-uae-logs")
        )
        self.assertEqual(rendered, expected)

    def test_missing_session_and_disk_fail_cleanly(self):
        with self.assertRaisesRegex(utmlib.UTMError, "session does not exist"):
            utmlib.render_runtime(SYSTEM, "absent", self.root)
        (self.session / "amix-system.hdf").unlink()
        with self.assertRaisesRegex(utmlib.UTMError, "incomplete session disk set"):
            self.render()

    def test_missing_rom_fails_cleanly_and_key_remains_operator_selected(self):
        (self.media / "amiga-os-310-a3000.rom").unlink()
        with self.assertRaisesRegex(utmlib.UTMError, "compatible-a3000-kickstart-rom"):
            self.render()
        (self.media / "amiga-os-310-a3000.rom").write_bytes(b"AMIROMTYPE1synthetic-rom")
        (self.media / "rom.key").unlink()
        self.assertNotIn("kickstart_key_file", self.render())

    def test_unencrypted_rom_does_not_require_key(self):
        (self.media / "amiga-os-310-a3000.rom").write_bytes(b"synthetic-unencrypted-rom")
        (self.media / "rom.key").unlink()
        text = self.render()
        self.assertNotIn("kickstart_key_file", text)

    def test_rendering_does_not_read_or_transform_rom_or_key(self):
        rom = self.media / "amiga-os-310-a3000.rom"
        key = self.media / "rom.key"
        original_open = Path.open

        def reject_media_reads(path, *args, **kwargs):
            if path in (rom, key):
                raise AssertionError(f"runtime attempted to inspect operator media: {path}")
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", reject_media_reads):
            text = self.render()
        self.assertIn(f"kickstart_file = {rom}", text)
        self.assertIn(f"kickstart_key_file = {key}", text)
        self.assertNotIn("operator-rom", text)

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

    def test_normal_stop_still_requires_an_explicit_safe_stop_mode(self):
        self.write_running_state()
        with mock.patch.object(utm, "pid_alive", return_value=True), \
             mock.patch.object(utm, "stop_process") as stop:
            with self.assertRaisesRegex(utmlib.UTMError, "exactly one"):
                utm.cmd_system_stop(self.stop_args())
        stop.assert_not_called()

    def test_guest_synced_stop_retains_attestation_semantics(self):
        state = self.write_running_state()
        with mock.patch.object(utm, "pid_alive", return_value=True), \
             mock.patch.object(utm, "stop_process", return_value=True) as stop:
            self.assertEqual(utm.cmd_system_stop(
                self.stop_args(guest_synced=True)), 0)
        stop.assert_called_once_with(424242, 0.25)
        termination = json.loads(state.read_text())["termination"]
        self.assertEqual(termination["kind"], "guest-synced")
        self.assertTrue(termination["guest_filesystems_synced"])
        # Existing --guest-synced semantics attest sync, not an OS shutdown.
        self.assertFalse(termination["clean_guest_shutdown"])

    def test_failed_boot_stops_only_recorded_child_and_records_abnormal_stop(self):
        state = self.write_running_state(pid=515151)
        log = self.session / "console.log"
        log.write_text("synthetic white Kickstart diagnostic\n")
        hdf_before = (self.session / "amix-system.hdf").read_bytes()
        golden = self.root / "golden" / SYSTEM
        golden.mkdir(parents=True)
        golden_disk = golden / "amix-system.hdf"
        golden_disk.write_bytes(b"synthetic immutable golden sentinel")
        golden_before = golden_disk.read_bytes()

        with mock.patch.object(utm, "pid_alive", return_value=True), \
             mock.patch.object(utm, "stop_process", return_value=True) as stop:
            self.assertEqual(utm.cmd_system_stop(
                self.stop_args(failed_boot=True)), 0)

        # The bounded stop helper receives only the supervised child PID.
        stop.assert_called_once_with(515151, 0.25)
        data = json.loads(state.read_text())
        self.assertEqual(data["runtime_status"], "stopped")
        self.assertEqual(data["termination"]["kind"], "failed-boot")
        self.assertFalse(data["termination"]["guest_filesystems_synced"])
        self.assertFalse(data["termination"]["clean_guest_shutdown"])
        self.assertIn("stopped_at", data["termination"])
        self.assertEqual(log.read_text(), "synthetic white Kickstart diagnostic\n")
        self.assertEqual((self.session / "amix-system.hdf").read_bytes(), hdf_before)
        self.assertEqual(golden_disk.read_bytes(), golden_before)

    def test_failed_boot_rejects_missing_stale_or_different_session(self):
        with self.assertRaisesRegex(utmlib.UTMError, "not running"):
            utm.cmd_system_stop(self.stop_args(failed_boot=True))
        self.write_running_state()
        with mock.patch.object(utm, "pid_alive", return_value=False):
            with self.assertRaisesRegex(utmlib.UTMError, "recorded process.*not running"):
                utm.cmd_system_stop(self.stop_args(failed_boot=True))
        with mock.patch.object(utm, "pid_alive") as alive:
            with self.assertRaisesRegex(utmlib.UTMError, "belongs to session synthetic"):
                utm.cmd_system_stop(self.stop_args(
                    failed_boot=True, session_id="another-session"))
        alive.assert_not_called()

    def test_stop_modes_are_mutually_exclusive_and_broker_cli_is_unchanged(self):
        parser = utm.parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["system", "stop", SYSTEM, "--guest-synced",
                               "--failed-boot"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["broker", "stop", "v7-session", "--failed-boot"])


if __name__ == "__main__":
    unittest.main()
