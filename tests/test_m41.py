import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import yaml

from scripts import fsuae_m41
from scripts.utmlib import UTMError


ROOT = Path(__file__).resolve().parents[1]


class M41Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media = self.root / "media/amix-a3000"
        self.media.mkdir(parents=True)
        self.rom = self.media / "operator-selected-rom"
        self.rom.write_bytes(b"synthetic test ROM, not historical media")
        self.rom.chmod(0o440)
        self.workspace = self.root / "staging/m41-test"

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, **changes):
        values = dict(root=str(self.root), workspace=str(self.workspace), rom=str(self.rom),
                      rom_key=None, rdb_size_mib=1)
        values.update(changes)
        return fsuae_m41.prepare(Namespace(**values))

    def test_debian_fsuae_provisioning_is_exact_auditable_and_minimal(self):
        defaults = yaml.safe_load(
            (ROOT / "ansible/roles/foundation/defaults/main.yml").read_text())
        tasks = yaml.safe_load(
            (ROOT / "ansible/roles/foundation/tasks/main.yml").read_text())
        self.assertEqual(defaults["utm_fsuae_package"], "fs-uae")
        self.assertEqual(defaults["utm_fsuae_version"], "3.1.66-2+b1")
        self.assertEqual(defaults["utm_fsuae_architecture"], "amd64")
        self.assertEqual(defaults["utm_fsuae_suite"], "trixie")
        self.assertEqual(defaults["utm_fsuae_component"], "main")
        self.assertRegex(defaults["utm_fsuae_deb_sha256"], r"^[0-9a-f]{64}$")
        apt_specs = [task["ansible.builtin.apt"]["name"] for task in tasks
                     if "ansible.builtin.apt" in task]
        self.assertIn("{{ utm_fsuae_package }}={{ utm_fsuae_version }}", apt_specs)
        serialized = (ROOT / "ansible/roles/foundation/tasks/main.yml").read_text().lower()
        self.assertNotIn("fs-uae-launcher", serialized)
        self.assertNotIn("fs-uae-device-helper", serialized)
        self.assertNotIn("xvfb", serialized)
        self.assertIn("changed_when: false", serialized)

    def test_probe_template_matches_pinned_source_contract_and_has_no_network(self):
        text = (ROOT / "systems/amix-a3000/m41-probe.fs-uae.in").read_text()
        expected = {
            "amiga_model": "A3000", "cpu": "68030", "mmu": "68030",
            "fpu": "68882", "chip_memory": "2048", "motherboard_ram": "16384",
            "jit_compiler": "0", "network_card": "0", "bsdsocket_library": "0",
            "hard_drive_0_type": "rdb", "hard_drive_0_controller": "scsi6",
            "stdout": "1", "uaelog": "1",
        }
        parsed = dict(line.split(" = ", 1) for line in text.splitlines()
                      if " = " in line)
        for key, value in expected.items():
            self.assertEqual(parsed[key], value)
        self.assertIn("tape0,ro", parsed["uae_uaehf1"])
        self.assertIn("scsi4", parsed["uae_uaehf1"])
        self.assertEqual(parsed["serial_port"], "@SERIAL_PTY@")
        self.assertIn("@ROM_KEY_OPTION@", text)
        self.assertEqual(parsed["logs_dir"], "@QUALIFICATION_LOG_DIR@")
        lowered = text.lower()
        for forbidden in ("tcp://", "slirp", "uae_tap", "bridge", "netplay_server", "a2065"):
            self.assertNotIn(forbidden, lowered)

    def test_prepare_observes_immutable_rom_and_creates_only_derived_probes(self):
        self.assertEqual(self.prepare(), 0)
        metadata = json.loads((self.workspace / "probe.json").read_text())
        self.assertEqual(metadata["status"], "HUMAN_REQUIRED")
        self.assertEqual(metadata["artifacts"]["rom"]["authenticity"], "UNPINNED")
        self.assertEqual(metadata["artifacts"]["rom"]["path"], str(self.rom))
        self.assertRegex(metadata["artifacts"]["rom"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual((self.workspace / "probe-rdb.hdf").stat().st_size, 1024 * 1024)
        self.assertEqual((self.workspace / "probe-tape/index.tape").read_text(),
                         "probe-member.bin\n")
        config = (self.workspace / "m41-probe.fs-uae").read_text()
        self.assertIn(str(self.rom), config)
        self.assertIn("@QUALIFICATION_PTY@", config)
        self.assertEqual(self.rom.read_bytes(), b"synthetic test ROM, not historical media")

    def test_optional_rom_key_is_validated_and_rendered_by_source_backed_option(self):
        key = self.media / "operator-selected-key"
        key.write_bytes(b"synthetic test key, not historical media")
        key.chmod(0o440)
        self.prepare(rom_key=str(key))
        metadata = json.loads((self.workspace / "probe.json").read_text())
        self.assertEqual(metadata["artifacts"]["rom_key"]["authenticity"], "UNPINNED")
        self.assertIn(f"kickstart_key_file = {key}",
                      (self.workspace / "m41-probe.fs-uae").read_text())

    def test_rom_validation_fails_closed_for_missing_writable_or_external_source(self):
        with self.assertRaisesRegex(UTMError, "missing or inaccessible"):
            self.prepare(rom=str(self.media / "missing"))
        self.rom.chmod(0o640)
        with self.assertRaisesRegex(UTMError, "no write bits"):
            self.prepare()
        self.rom.chmod(0o440)
        outside = self.root / "outside-rom"; outside.write_bytes(b"x"); outside.chmod(0o440)
        with self.assertRaisesRegex(UTMError, "beneath"):
            self.prepare(rom=str(outside))

    def test_prepare_refuses_overwrite_and_protected_nonstaging_destination(self):
        self.prepare()
        with self.assertRaisesRegex(UTMError, "new directory beneath staging"):
            self.prepare()
        other = self.root / "sessions/probe"
        with self.assertRaisesRegex(UTMError, "new directory beneath staging"):
            self.prepare(workspace=str(other))

    def test_missing_display_is_human_required_not_pass(self):
        self.prepare()
        output = StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            result = fsuae_m41.qualify(Namespace(workspace=str(self.workspace), observe_seconds=1))
        self.assertEqual(result, 2)
        self.assertIn("HUMAN_REQUIRED", output.getvalue())
        self.assertFalse((self.workspace / "qualification.json").exists())

    def detailed_log(self, slave="/dev/pts/10"):
        metadata = json.loads((self.workspace / "probe.json").read_text())
        rdb = metadata["probe_rdb"]
        tape = metadata["synthetic_tape"]
        rom = metadata["artifacts"]["rom"]["path"]
        return "\n".join((
            'config match for "A3000"',
            'set option "chipmem_size" to "4" (result: 1)',
            'set option "a3000mem_size" to "16" (result: 1)',
            "CPU=68030, FPU=68882, MMU=68030, JIT=0.",
            "Initializing A3000 mainboard SCSI",
            "hard drive type explicitly set to rdb", "rdb mode: 1",
            f"Adding A3000 mainboard SCSI HD unit 6 ({rdb})",
            f"hfd open: '{rdb}'",
            f"HDF '{rdb}' opened, size=1024K mode=3 empty=0",
            f"Adding A3000 mainboard SCSI TAPE unit 4 ({tape})",
            f"TAPEEMU INDEX: '{tape}/index.tape'",
            f"serial port device: {slave}",
            f"serial: open '{slave}' -> fd=22",
            f"read_rom_name {rom}",
            "ROM: SHA1=864bf136c5997d9c0c9fa89ce62249364bb19859",
            f"Unknown ROM '{rom}' loaded", "SDL_QUIT",
        ))

    def evidence_files(self, stdout=""):
        detailed = self.workspace / "current-fs-uae.log.txt"
        detailed.write_text(self.detailed_log())
        stdout_path = self.workspace / "fs-uae-stdout.log"
        stdout_path.write_text(stdout)
        return detailed, stdout_path, self.workspace / "m41-probe.fs-uae"

    def test_sparse_diagnostics_and_complete_current_detailed_log_pass(self):
        self.prepare()
        metadata = json.loads((self.workspace / "probe.json").read_text())
        boundary = os.stat(self.workspace).st_mtime_ns
        detailed, stdout, config = self.evidence_files()
        evidence, missing = fsuae_m41.validate_run_log(
            detailed, stdout, config, boundary, metadata, "/dev/pts/10")
        self.assertEqual(missing, [])
        self.assertTrue(evidence["rdb_hd_unit_6"])
        self.assertTrue(evidence["serial_opened"])
        sparse_stdout_stderr = "FS-UAE 3.1.66 starting\n"
        self.assertNotIn("CPU=68030", sparse_stdout_stderr)

    def test_incomplete_or_stale_detailed_log_fails_closed(self):
        self.prepare()
        metadata = json.loads((self.workspace / "probe.json").read_text())
        detailed = self.workspace / "fs-uae.log.txt"
        detailed.write_text('config match for "A3000"\n')
        stdout = self.workspace / "fs-uae-stdout.log"; stdout.write_text("")
        config = self.workspace / "m41-probe.fs-uae"
        _, missing = fsuae_m41.validate_run_log(
            detailed, stdout, config, 0, metadata, "/dev/pts/10")
        self.assertIn("cpu_fpu_mmu_jit", missing)
        future_boundary = detailed.stat().st_mtime_ns + 1
        with self.assertRaisesRegex(UTMError, "predates the current run boundary"):
            fsuae_m41.validate_run_log(
                detailed, stdout, config, future_boundary, metadata, "/dev/pts/10")

    def test_encrypted_unknown_rom_records_attested_load_without_identity_claim(self):
        encrypted = self.media / "operator-selected-encrypted-rom"
        encrypted.write_bytes(b"AMIROMTYPE1" + b"synthetic encrypted payload")
        encrypted.chmod(0o440)
        key = self.media / "operator-selected-key"
        key.write_bytes(b"synthetic test key, not historical media")
        key.chmod(0o440)
        self.prepare(rom=str(encrypted), rom_key=str(key))
        metadata = json.loads((self.workspace / "probe.json").read_text())
        detailed, stdout, config = self.evidence_files(
            "UAE: KS ROM 2cf0789e (524288 bytes)\n")
        evidence, missing = fsuae_m41.validate_run_log(
            detailed, stdout, config, 0, metadata, "/dev/pts/10")
        self.assertEqual(missing, [])
        self.assertTrue(evidence["encrypted_source_amiromtype1"])
        self.assertTrue(evidence["encrypted_rom_key_configured"])
        self.assertTrue(evidence["encrypted_rom_loaded_512k"])
        self.assertTrue(evidence["rom_identity_unknown"])

    def test_rdb_and_encrypted_rom_attestation_failures_remain_closed(self):
        encrypted = self.media / "operator-selected-encrypted-rom"
        encrypted.write_bytes(b"AMIROMTYPE1" + b"synthetic encrypted payload")
        encrypted.chmod(0o440)
        key = self.media / "operator-selected-key"
        key.write_bytes(b"synthetic test key, not historical media")
        key.chmod(0o440)
        self.prepare(rom=str(encrypted), rom_key=str(key))
        metadata = json.loads((self.workspace / "probe.json").read_text())
        complete = self.detailed_log()
        stdout_text = "UAE: KS ROM 2cf0789e (524288 bytes)\n"

        cases = {
            "missing RDB open": (complete.replace("hfd open:", "hfd absent:"),
                                 stdout_text, None, "rdb_opened"),
            "missing configured key": (complete, stdout_text,
                                       "kickstart_key_file", "encrypted_rom_key_configured"),
            "missing runtime ROM load": (complete.replace("Unknown ROM", "ROM absent"),
                                         stdout_text, None, "rom_loaded"),
        }
        for name, (log_text, out_text, remove_config_line, expected) in cases.items():
            with self.subTest(name=name):
                detailed = self.workspace / f"{name.replace(' ', '-')}.log"
                detailed.write_text(log_text)
                stdout = self.workspace / f"{name.replace(' ', '-')}.stdout"
                stdout.write_text(out_text)
                config = self.workspace / f"{name.replace(' ', '-')}.fs-uae"
                config_text = (self.workspace / "m41-probe.fs-uae").read_text()
                if remove_config_line:
                    config_text = "\n".join(
                        line for line in config_text.splitlines()
                        if remove_config_line not in line)
                config.write_text(config_text)
                _, missing = fsuae_m41.validate_run_log(
                    detailed, stdout, config, 0, metadata, "/dev/pts/10")
                self.assertIn(expected, missing)

        encrypted.chmod(0o640)
        encrypted.write_bytes(b"NOTAMIROM1" + b"synthetic encrypted payload")
        encrypted.chmod(0o440)
        detailed, stdout, config = self.evidence_files(stdout_text)
        _, missing = fsuae_m41.validate_run_log(
            detailed, stdout, config, 0, metadata, "/dev/pts/10")
        self.assertIn("encrypted_source_amiromtype1", missing)

    def test_provenance_fails_closed_off_debian_13(self):
        args = Namespace(expected_version="3.1.66-2+b1", expected_architecture="amd64",
                         suite="trixie", component="main", deb_filename="x", deb_sha256="0" * 64)
        with mock.patch.object(Path, "read_text", return_value='ID="ubuntu"\nVERSION_ID="26.04"\n'), \
             self.assertRaisesRegex(UTMError, "requires Debian 13"):
            fsuae_m41.provenance(args)

    def test_provenance_records_exact_package_binary_dependencies_and_origin(self):
        args = Namespace(expected_version="3.1.66-2+b1", expected_architecture="amd64",
                         suite="trixie", component="main",
                         deb_filename="pool/main/f/fs-uae/fs-uae_3.1.66-2+b1_amd64.deb",
                         deb_sha256="5f703e361d242a99da46454a0b21aafed6010e4153682f1aeed9f59e5cd3d9e4")
        def output(argv):
            if argv[:2] == ["dpkg-query", "-W"] and argv[-1] == "fs-uae":
                return "3.1.66-2+b1\tamd64"
            if argv[0] == "dpkg-query":
                return "qualified-dependency-version"
            if argv == ["/usr/bin/fs-uae", "--version"]:
                return "FS-UAE 3.1.66"
            if argv[:2] == ["apt-cache", "policy"]:
                return "Installed: 3.1.66-2+b1\n  https://deb.debian.org/debian trixie/main"
            self.fail(argv)
        captured = StringIO()
        real_read = Path.read_text
        def read_text(path, *call_args, **call_kwargs):
            if str(path) == "/etc/os-release":
                return 'ID="debian"\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13 (trixie)"\n'
            return real_read(path, *call_args, **call_kwargs)
        with mock.patch.object(Path, "read_text", read_text), \
             mock.patch.object(Path, "is_file", return_value=True), \
             mock.patch.object(os, "access", return_value=True), \
             mock.patch.object(fsuae_m41, "command_output", side_effect=output), \
             mock.patch.object(fsuae_m41, "sha256", return_value="a" * 64), \
             redirect_stdout(captured):
            self.assertEqual(fsuae_m41.provenance(args), 0)
        report = json.loads(captured.getvalue())
        self.assertEqual(report["package_version"], "3.1.66-2+b1")
        self.assertEqual(report["architecture"], "amd64")
        self.assertEqual(report["executable"], "/usr/bin/fs-uae")
        self.assertEqual(report["executable_sha256"], "a" * 64)
        self.assertEqual(set(report["dependencies"]), set(fsuae_m41.RUNTIME_DEPENDENCIES))
        self.assertIn("trixie/main", "\n".join(report["apt_policy"]))

    def test_provenance_json_is_deterministic_for_idempotent_publication(self):
        report = {"package": "fs-uae", "version": "3.1.66-2+b1",
                  "dependencies": {"libc6": "2.41-12"}}
        first = json.dumps(report, sort_keys=True, separators=(",", ":"))
        second = json.dumps(report, sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)

    def test_m1_m2_m3_status_and_amix_golden_atomicity_are_unchanged(self):
        for system_id in ("unix-v7-pdp11", "43bsd-vax"):
            manifest = yaml.safe_load((ROOT / f"systems/{system_id}/system.yml").read_text())
            self.assertEqual(manifest["status"], "complete")
        tasks = yaml.safe_load((ROOT / "ansible/roles/foundation/tasks/main.yml").read_text())
        golden_paths = [task["ansible.builtin.file"].get("path") for task in tasks
                        if "ansible.builtin.file" in task and "golden" in str(task)]
        self.assertNotIn("/srv/unix-time-machine/golden/amix-a3000", golden_paths)


if __name__ == "__main__":
    unittest.main()
