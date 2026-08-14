import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ProvisioningContractTests(unittest.TestCase):
    def setUp(self):
        self.defaults = yaml.safe_load(
            (ROOT / "ansible/roles/foundation/defaults/main.yml").read_text()
        )
        self.tasks = yaml.safe_load(
            (ROOT / "ansible/roles/foundation/tasks/main.yml").read_text()
        )

    def test_simh_source_is_immutable_and_integrity_pinned(self):
        commit = self.defaults["utm_simh_commit"]
        digest = self.defaults["utm_simh_archive_sha256"]
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertIn("{{ utm_simh_commit }}", self.defaults["utm_simh_archive_url"])
        self.assertNotRegex(self.defaults["utm_simh_archive_url"], r"/(master|main|HEAD)(?:[./]|$)")
        get_urls = [task["ansible.builtin.get_url"] for task in self.tasks
                    if "ansible.builtin.get_url" in task]
        self.assertEqual(get_urls[0]["checksum"], "sha256:{{ utm_simh_archive_sha256 }}")

    def test_debian_13_source_build_replaces_unavailable_binary_package(self):
        assertion = self.tasks[0]["ansible.builtin.assert"]["that"]
        self.assertIn('ansible_distribution == "Debian"', assertion)
        self.assertIn('ansible_distribution_major_version == "13"', assertion)
        apt = next(task["ansible.builtin.apt"] for task in self.tasks
                   if "ansible.builtin.apt" in task)
        for dependency in ("ca-certificates", "gcc", "gzip", "libc6-dev", "make", "tar"):
            self.assertIn(dependency, apt["name"])
        self.assertNotIn("simh", apt["name"])
        self.assertFalse(any("ansible.builtin.apt_repository" in task for task in self.tasks))

    def test_build_is_minimal_networkless_and_idempotency_guarded(self):
        build = next(task for task in self.tasks
                     if task.get("name") == "Build and install the pinned PDP-11 simulator")
        self.assertEqual(build["when"], "not utm_simh_install_current")
        command = next(task["ansible.builtin.command"] for task in build["block"]
                       if task.get("name", "").startswith("Build only"))
        self.assertEqual(command["argv"], ["make", "pdp11", "NONETWORK=1"])
        cleanup = build["always"][0]["ansible.builtin.file"]
        self.assertEqual(cleanup["state"], "absent")

    def test_canonical_provision_entry_point_owns_ansible_resolution(self):
        makefile = (ROOT / "Makefile").read_text()
        recipe = re.search(r"^provision:\n((?:\t.*\n)+)", makefile, re.MULTILINE)
        self.assertIsNotNone(recipe)
        command = recipe.group(1)
        self.assertIn("ANSIBLE_CONFIG=$(ANSIBLE_CONFIG_FILE)", command)
        self.assertIn("-i $(ANSIBLE_INVENTORY)", command)
        self.assertIn("$(ANSIBLE_PLAYBOOK)", command)
        config = (ROOT / "ansible/ansible.cfg").read_text()
        self.assertRegex(config, r"(?m)^roles_path = roles$")

    def test_manifest_and_provisioning_agree_on_canonical_binary(self):
        manifest = yaml.safe_load((ROOT / "systems/unix-v7-pdp11/system.yml").read_text())
        expected = self.defaults["utm_simh_prefix"] + "/pdp11"
        expected = expected.replace("{{ utm_simh_version }}", self.defaults["utm_simh_version"])
        self.assertEqual(manifest["emulator"]["executable"], expected)

    def test_operator_enrollment_is_explicit_and_idempotent(self):
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("operator-add:", makefile)
        self.assertIn("utm_operator_user=$(USER)", makefile)
        play = yaml.safe_load((ROOT / "ansible/playbooks/operator-add.yml").read_text())[0]
        tasks = play["tasks"]
        user = next(task["ansible.builtin.user"] for task in tasks if "ansible.builtin.user" in task)
        self.assertEqual(user["name"], "{{ utm_operator_user }}")
        self.assertEqual(user["groups"], ["unix-time-machine"])
        self.assertTrue(user["append"])
        self.assertTrue(any("ansible.builtin.getent" in task for task in tasks))

    def test_golden_publication_target_has_operator_read_only_ownership(self):
        task = next(task for task in self.tasks
                    if task.get("name") == "Create immutable golden publication target")
        contract = task["ansible.builtin.file"]
        self.assertEqual(contract["owner"], "root")
        self.assertEqual(contract["group"], "unix-time-machine")
        self.assertEqual(contract["mode"], "0750")

    def test_implemented_system_media_directories_are_inventory_driven_and_protected(self):
        self.assertEqual(
            self.defaults["utm_implemented_systems"],
            ["unix-v7-pdp11", "43bsd-vax", "amix-a3000"],
        )
        task = next(task for task in self.tasks
                    if task.get("name") == "Create protected per-system media directories")
        contract = task["ansible.builtin.file"]
        self.assertEqual(contract["path"], "/srv/unix-time-machine/media/{{ item }}")
        self.assertEqual(task["loop"], "{{ utm_implemented_systems }}")
        self.assertEqual(contract["owner"], "root")
        self.assertEqual(contract["group"], "unix-time-machine")
        self.assertEqual(contract["mode"], "2750")

    def test_staging_is_service_group_writable_and_setgid(self):
        task = next(task for task in self.tasks
                    if task.get("name") == "Allow the service account to create runtime state")
        contract = task["ansible.builtin.file"]
        self.assertIn("staging", task["loop"])
        self.assertEqual(contract["owner"], "unix-time-machine")
        self.assertEqual(contract["group"], "unix-time-machine")
        self.assertEqual(contract["mode"], "2770")

    def test_no_canonical_directory_is_world_writable(self):
        for task in self.tasks:
            contract = task.get("ansible.builtin.file")
            if not contract or contract.get("state") != "directory":
                continue
            mode = contract.get("mode")
            if mode is not None:
                self.assertEqual(int(mode, 8) & 0o002, 0, task.get("name"))


if __name__ == "__main__":
    unittest.main()
