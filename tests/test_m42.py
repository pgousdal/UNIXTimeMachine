import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import amix_m42
from scripts.utmlib import UTMError, sha256


ROOT = Path(__file__).resolve().parents[1]


class M42Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media = self.root / "media/amix-a3000"
        self.media.mkdir(parents=True)
        self.boot = self.media / "operator-observed-one"
        self.root_floppy = self.media / "operator-observed-two"
        self.rom = self.media / "operator-rom"
        self.key = self.media / "operator-key"
        for path, data in ((self.boot, b"boot"), (self.root_floppy, b"root"),
                           (self.rom, b"AMIROMTYPE1rom"), (self.key, b"key")):
            path.write_bytes(data); path.chmod(0o440)
        self.tape = self.media / "observed-tape-directory"
        self.tape.mkdir()
        self.members = []
        for name, data in (("segment-z", b"z"), ("segment-a", b"a")):
            path = self.tape / name; path.write_bytes(data); path.chmod(0o440)
            self.members.append(path)
        self.index = self.tape / "operator-observed-index"
        self.index.write_text("segment-z\nsegment-a\n"); self.index.chmod(0o440)
        self.spec = self.root / "operator-spec.json"
        self.write_spec()
        self.inventory = self.root / "reports/amix-a3000/observed.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_spec(self):
        self.spec.write_text(json.dumps({
            "boot_floppy": {"path": str(self.boot),
                            "source_description": "operator supplied description one"},
            "root_install_floppy": {"path": str(self.root_floppy),
                                    "source_description": "operator supplied description two"},
            "installation_tape": {"directory": str(self.tape),
                                  "index_path": str(self.index),
                                  "source_description": "operator supplied tape provenance"},
        }))

    def make_inventory(self):
        return amix_m42.inventory_amix(self.spec, self.inventory, self.root)

    def test_inventory_records_observed_names_hashes_descriptions_and_exact_order(self):
        self.make_inventory()
        data = json.loads(self.inventory.read_text())
        self.assertEqual(data["authentication"], "observed-local-provenance-only")
        self.assertEqual(data["artifacts"]["boot_floppy"]["observed_filename"],
                         "operator-observed-one")
        self.assertEqual(data["artifacts"]["boot_floppy"]["sha256"], sha256(self.boot))
        self.assertEqual(data["artifacts"]["boot_floppy"]["writable_use"],
                         "private-staging-copy-required")
        order = data["artifacts"]["installation_tape"]["member_order"]
        self.assertEqual([member["observed_filename"] for member in order],
                         ["segment-z", "segment-a"])
        self.assertEqual(data["artifacts"]["installation_tape"]["index"]
                         ["observed_filename"], "operator-observed-index")
        self.assertEqual(data["artifacts"]["installation_tape"]["attachment"],
                         "private-staging-representation-required")

    def test_inventory_fails_for_missing_duplicate_or_ambiguous_tape_members(self):
        self.index.chmod(0o640); self.index.write_text("segment-z\nmissing\n"); self.index.chmod(0o440)
        with self.assertRaisesRegex(UTMError, "missing or inaccessible"):
            self.make_inventory()
        self.index.chmod(0o640); self.index.write_text("segment-z\nsegment-z\n"); self.index.chmod(0o440)
        with self.assertRaisesRegex(UTMError, "duplicate"):
            self.make_inventory()
        self.index.chmod(0o640); self.index.write_text("segment-z\nsegment-a\n"); self.index.chmod(0o440)
        extra = self.tape / "not-in-index"; extra.write_bytes(b"x"); extra.chmod(0o440)
        with self.assertRaisesRegex(UTMError, "ambiguous"):
            self.make_inventory()

    def test_inventory_requires_immutable_protected_sources_and_descriptions(self):
        self.boot.chmod(0o640)
        with self.assertRaisesRegex(UTMError, "no write bits"):
            self.make_inventory()
        self.boot.chmod(0o440)
        spec = json.loads(self.spec.read_text()); spec["boot_floppy"]["source_description"] = ""
        self.spec.write_text(json.dumps(spec))
        with self.assertRaisesRegex(UTMError, "source description"):
            self.make_inventory()

    def test_prepare_creates_writable_floppies_fresh_rdb_and_two_configs(self):
        self.make_inventory()
        before = {path: sha256(path) for path in (self.boot, self.root_floppy, *self.members)}
        workspace = self.root / "staging/base-install"
        amix_m42.prepare_amix(self.inventory, workspace, self.root,
                             self.rom, self.key, 1)
        metadata = json.loads((workspace / "install.json").read_text())
        self.assertEqual(metadata["base_release_target"],
                         "base AMIX 2.1 installation staging")
        self.assertFalse(metadata["golden_created"])
        self.assertFalse(metadata["patch_media_used"])
        self.assertFalse(metadata["serial_getty_configured"])
        self.assertEqual(metadata["rdb"]["backing_file_size"], 1024 * 1024)
        self.assertEqual(metadata["rdb"]["final_geometry"], "HUMAN_REQUIRED")
        self.assertEqual((workspace / "base-amix-2.1-installation-staging.hdf").stat().st_size,
                         1024 * 1024)
        for key in ("boot_floppy", "root_install_floppy"):
            copy = Path(metadata["floppy_copies"][key]["output_path"])
            self.assertEqual(copy.stat().st_mode & 0o777, 0o640)
            self.assertEqual(metadata["floppy_copies"][key]["source_sha256"],
                             metadata["floppy_copies"][key]["output_sha256_before_first_boot"])
        install = (workspace / "install.fs-uae").read_text()
        self.assertIn("hard_drive_0_controller = scsi6", install)
        self.assertIn("tape0,ro", install); self.assertIn("scsi4", install)
        self.assertIn("floppy_drive_0", install); self.assertIn("floppy_image_1", install)
        self.assertIn("network_card = 0", install)
        tape_staging = workspace / "installation-tape.staging"
        self.assertEqual((tape_staging / "index.tape").read_text(),
                         "segment-z\nsegment-a\n")
        self.assertEqual(metadata["tape_attachment"]["mode"],
                         "read-only-private-staging-representation")
        self.assertEqual(len(metadata["tape_attachment"]["copy_methods"]), 2)
        for forbidden in ("serial_port", "getty", "patch", "tcp://", "slirp", "a2065"):
            self.assertNotIn(forbidden, install.lower())
        first_boot = (workspace / "base-first-boot.fs-uae").read_text()
        self.assertNotIn("floppy_", first_boot); self.assertNotIn("tape0", first_boot)
        self.assertIn("scsi6", first_boot)
        self.assertEqual(before, {path: sha256(path) for path in before})
        evidence = json.loads((workspace / "installation-evidence.json").read_text())
        self.assertEqual(evidence["installer_completion"], "HUMAN_REQUIRED")

    def test_exact_fsuae_index_representation_is_attached_read_only(self):
        self.index.chmod(0o640)
        exact = self.tape / "index.tape"
        self.index.rename(exact); exact.chmod(0o440); self.index = exact
        self.write_spec(); self.make_inventory()
        data = json.loads(self.inventory.read_text())
        self.assertEqual(data["artifacts"]["installation_tape"]["attachment"],
                         "read-only-source-directory")
        workspace = self.root / "staging/source-tape"
        amix_m42.prepare_amix(self.inventory, workspace, self.root,
                             self.rom, self.key, 1)
        metadata = json.loads((workspace / "install.json").read_text())
        self.assertEqual(metadata["tape_attachment"]["mode"],
                         "read-only-source-directory")
        self.assertEqual(metadata["tape_attachment"]["directory"], str(self.tape))
        self.assertFalse((workspace / "installation-tape.staging").exists())

    def test_prepare_fails_on_changed_source_and_refuses_overwrite(self):
        self.make_inventory()
        self.boot.chmod(0o640); self.boot.write_bytes(b"changed"); self.boot.chmod(0o440)
        with self.assertRaisesRegex(UTMError, "no longer matches inventory"):
            amix_m42.prepare_amix(self.inventory, self.root / "staging/changed",
                                 self.root, self.rom, self.key, 1)
        self.boot.chmod(0o640); self.boot.write_bytes(b"boot"); self.boot.chmod(0o440)
        workspace = self.root / "staging/existing"; workspace.mkdir(parents=True)
        with self.assertRaisesRegex(UTMError, "new directory beneath staging"):
            amix_m42.prepare_amix(self.inventory, workspace, self.root,
                                 self.rom, self.key, 1)

    def test_failure_workspace_is_preserved_and_no_golden_is_created(self):
        self.make_inventory()
        workspace = self.root / "staging/preserved-failure"
        with mock.patch.object(amix_m42, "config_text", side_effect=UTMError("render failure")), \
             self.assertRaisesRegex(UTMError, "render failure"):
            amix_m42.prepare_amix(self.inventory, workspace, self.root,
                                 self.rom, self.key, 1)
        self.assertTrue(workspace.is_dir())
        self.assertTrue((workspace / "boot-floppy.staging").is_file())
        self.assertFalse((self.root / "golden/amix-a3000").exists())

    def test_status_boundaries_preserve_completed_milestones(self):
        for system_id in ("unix-v7-pdp11", "43bsd-vax"):
            manifest = yaml.safe_load((ROOT / f"systems/{system_id}/system.yml").read_text())
            self.assertEqual(manifest["status"], "complete")
        amix = yaml.safe_load((ROOT / "systems/amix-a3000/system.yml").read_text())
        self.assertEqual(amix["status"], "defined")
        self.assertEqual(amix["milestones"]["m4.1"], "complete")
        self.assertEqual(amix["milestones"]["m4.2"],
                         "implemented-awaiting-real-host-qualification")


if __name__ == "__main__":
    unittest.main()
