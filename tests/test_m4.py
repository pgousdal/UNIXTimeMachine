import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import yaml

from broker.backend import Backend, ConsoleTransport, PreparedSession, ShutdownProtocol
from broker.config import BrokerConfig
from broker.manager import Broker
from broker.process import process_start_ticks
from broker.store import Store
from scripts.utmlib import UTMError, atomic_json, sha256, verify_media


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = "amix-a3000"


class ExternalConsoleTestBackend(Backend):
    """Architecture test double only; it is not an FS-UAE implementation."""

    def prepare(self, system_id, session_id, root):
        workspace = root / "sessions" / system_id / session_id
        workspace.mkdir(parents=True)
        return PreparedSession(workspace, ["must-not-run"], ["login:"], [], {},
                               ConsoleTransport.external_pty())

    def shutdown_protocol(self):
        return ShutdownProtocol(True, b"", b"halted", b"")


class M40Tests(unittest.TestCase):
    def manifest(self):
        return yaml.safe_load((ROOT / "systems/amix-a3000/system.yml").read_text())

    def test_amix_manifest_is_conservative_incomplete_and_network_disabled(self):
        manifest = self.manifest()
        self.assertEqual(manifest["status"], "runtime-implemented-real-host-qualification-pending")
        self.assertEqual(manifest["session"]["network"], "disabled")
        self.assertFalse(manifest["session"]["public_eligible"])
        self.assertEqual(manifest["emulator"]["implementation"], "graphical-session-runtime")
        self.assertEqual(manifest["emulator"]["jit"], "disabled")
        self.assertTrue(manifest["canonical_target"]["result_qualification_required"])
        self.assertEqual(manifest["milestones"]["m4.1"], "complete")

    def test_amix_media_are_logical_external_unpinned_without_names_or_hashes(self):
        manifest = self.manifest()
        self.assertEqual(manifest["media"]["policy"], "external")
        self.assertEqual(manifest["media"]["authenticity"], "unpinned")
        items = manifest["media"]["items"]
        self.assertEqual({item["logical_name"] for item in items}, {
            "amix-2.1-boot-floppy", "amix-2.1-root-install-floppy",
            "amix-2.1-installation-tape", "official-amix-2.1-patch-floppy",
            "compatible-a3000-kickstart-rom", "rom-key",
        })
        for item in items:
            self.assertEqual(item["operator_path"], "explicit")
            self.assertNotIn("sha256", item)
            self.assertNotIn("sha1", item)
            self.assertNotIn("size", item)
        tape = next(item for item in items if item["logical_name"].endswith("installation-tape"))
        self.assertEqual(tape["representation"], "ordered-multi-member-tape")
        self.assertEqual(tape["ordering"], "operator-supplied-and-recorded")
        self.assertFalse(next(item for item in items if item["logical_name"] == "rom-key")["required"])
        rom = next(item for item in items if item["logical_name"] == "compatible-a3000-kickstart-rom")
        key = next(item for item in items if item["logical_name"] == "rom-key")
        self.assertEqual(rom["filenames"], ["amiga-os-310-a3000.rom"])
        self.assertEqual(key["filenames"], ["rom.key"])

    def test_unmapped_amix_media_fail_without_authenticity_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            results = verify_media(SYSTEM, Path(directory))
        self.assertEqual(len(results), 6)
        required = [result for result in results if result.logical_name != "rom-key"]
        self.assertTrue(all(result.status == "MISSING" for result in required))
        self.assertTrue(all(result.detail for result in required))
        self.assertEqual(next(result for result in results if result.logical_name == "rom-key").status,
                         "PASS")

    def test_backend_capabilities_describe_stdio_and_external_console_topologies(self):
        stdio = ConsoleTransport.stdio_pty().as_dict()
        external = ConsoleTransport.external_pty().as_dict()
        self.assertEqual(stdio["kind"], "stdio-pty")
        self.assertFalse(stdio["separate_diagnostics"])
        self.assertEqual(external["kind"], "external-pty")
        self.assertTrue(external["authoritative"])
        self.assertTrue(external["separate_diagnostics"])
        shutdown = ShutdownProtocol(True, b"\x05", b"sim>", b"quit\r").as_dict()
        self.assertEqual(shutdown["driver"], "simh-monitor")
        self.assertEqual(shutdown["monitor_enter_hex"], "05")

    def test_unimplemented_external_console_fails_closed_and_preserves_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic_json(root / "state/broker-config.json",
                        BrokerConfig(startup_timeout=1, readiness_timeout=1, idle_timeout=2,
                                     absolute_timeout=3, shutdown_timeout=.2).as_dict())
            with mock.patch("broker.manager.backend_for", return_value=ExternalConsoleTestBackend()), \
                 self.assertRaisesRegex(UTMError, "supervisor exited during startup"):
                Broker(root).request(SYSTEM, "external-contract")
            record = Store(root).load("external-contract")
            self.assertEqual(record.state, "failed")
            self.assertTrue((root / "sessions/amix-a3000/external-contract").is_dir())
            diagnostics = (root / "logs/sessions/external-contract/supervisor.log").read_text()
            self.assertIn("unsupported console transport", diagnostics)
            self.assertIsNone(process_start_ticks(record.emulator_pid))

    def test_completed_milestone_statuses_are_unchanged(self):
        for system_id in ("unix-v7-pdp11", "43bsd-vax"):
            manifest = yaml.safe_load((ROOT / f"systems/{system_id}/system.yml").read_text())
            self.assertEqual(manifest["status"], "complete")
        roadmap = (ROOT / "docs/ROADMAP.md").read_text()
        for milestone in ("M1", "M2", "M3"):
            section = roadmap.split(f"## {milestone} ", 1)[1].split("## ", 1)[0]
            self.assertIn("COMPLETE", section)


if __name__ == "__main__":
    unittest.main()
