#!/usr/bin/env python3
"""Preservation-safe M4.2 AMIX media inventory and installation staging."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

try:
    from .utmlib import UTMError, atomic_json, copy_exclusive, sha256
except ImportError:
    from utmlib import UTMError, atomic_json, copy_exclusive, sha256


SYSTEM_ID = "amix-a3000"
FORBIDDEN = ("tcp://", "slirp", "uae_tap", "bridge", "netplay", "a2065")


def immutable_file(path: Path, media_root: Path, role: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
        info = resolved.stat()
    except OSError as exc:
        raise UTMError(f"{role} missing or inaccessible: {exc}") from exc
    root = media_root.resolve(strict=True)
    if root not in resolved.parents or not stat.S_ISREG(info.st_mode):
        raise UTMError(f"{role} must be a regular file beneath {root}")
    if info.st_mode & 0o222:
        raise UTMError(f"{role} canonical source must have no write bits: {resolved}")
    return resolved


def described_file(entry: object, media_root: Path, role: str) -> dict:
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise UTMError(f"{role} requires an explicit path")
    description = entry.get("source_description")
    if not isinstance(description, str) or not description.strip():
        raise UTMError(f"{role} requires the operator's acquisition/source description")
    path = immutable_file(Path(entry["path"]), media_root, role)
    return {
        "authenticity": "UNPINNED",
        "byte_size": path.stat().st_size,
        "logical_role": role,
        "observed_filename": path.name,
        "observed_path": str(path),
        "sha256": sha256(path),
        "source_description": description.strip(),
    }


def inventory_amix(spec_path: Path, output: Path, host_root: Path) -> Path:
    if output.exists():
        raise UTMError(f"refusing to overwrite media inventory: {output}")
    reports = (host_root / "reports" / SYSTEM_ID).resolve()
    destination = output.resolve()
    if reports not in destination.parents:
        raise UTMError(f"AMIX inventory must be a new file beneath {reports}")
    try:
        spec = json.loads(spec_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise UTMError(f"cannot read AMIX inventory specification: {exc}") from exc
    if not isinstance(spec, dict):
        raise UTMError("AMIX inventory specification must be a JSON object")
    expected_roles = {"boot_floppy", "root_install_floppy", "installation_tape"}
    if set(spec) != expected_roles:
        raise UTMError("AMIX inventory requires exactly these roles: " +
                       ", ".join(sorted(expected_roles)))
    media_root = host_root / "media" / SYSTEM_ID
    artifacts = {
        "boot_floppy": described_file(spec.get("boot_floppy"), media_root, "boot-floppy"),
        "root_install_floppy": described_file(
            spec.get("root_install_floppy"), media_root, "root-install-floppy"),
    }
    tape = spec.get("installation_tape")
    if not isinstance(tape, dict):
        raise UTMError("installation-tape requires an explicit directory and index path")
    description = tape.get("source_description")
    if not isinstance(description, str) or not description.strip():
        raise UTMError("installation-tape requires the operator's acquisition/source description")
    try:
        tape_dir = Path(tape["directory"]).resolve(strict=True)
    except (KeyError, OSError) as exc:
        raise UTMError(f"installation-tape directory missing or inaccessible: {exc}") from exc
    media_resolved = media_root.resolve(strict=True)
    if media_resolved not in tape_dir.parents or not tape_dir.is_dir():
        raise UTMError(f"installation-tape directory must be beneath {media_resolved}")
    index = immutable_file(Path(tape.get("index_path", "")), media_root, "tape-order-index")
    if index.parent != tape_dir:
        raise UTMError("tape-order-index must be inside the installation-tape directory")
    lines = index.read_text().splitlines()
    if not lines or any(not line.strip() for line in lines):
        raise UTMError("tape ordering is empty or ambiguous")
    names = [line.strip() for line in lines]
    if len(names) != len(set(names)):
        raise UTMError("tape ordering contains duplicate members")
    members = []
    for position, name in enumerate(names):
        if Path(name).name != name or name in {".", ".."}:
            raise UTMError(f"unsafe or ambiguous tape member name: {name!r}")
        member = immutable_file(tape_dir / name, media_root, f"tape-member-{position}")
        members.append({
            "byte_size": member.stat().st_size, "observed_filename": name,
            "observed_path": str(member), "position": position,
            "sha256": sha256(member),
        })
    unreferenced = sorted(
        path.name for path in tape_dir.iterdir()
        if path.is_file() and path != index and path.name not in set(names))
    if unreferenced:
        raise UTMError("ambiguous tape directory has unreferenced files: " + ", ".join(unreferenced))
    artifacts["installation_tape"] = {
        "attachment": ("read-only-source-directory" if index.name == "index.tape"
                       else "private-staging-representation-required"),
        "authenticity": "UNPINNED",
        "directory": str(tape_dir),
        "index": {"byte_size": index.stat().st_size, "observed_filename": index.name,
                  "observed_path": str(index), "sha256": sha256(index)},
        "logical_role": "installation-tape",
        "member_order": members,
        "source_description": description.strip(),
    }
    for key in ("boot_floppy", "root_install_floppy"):
        artifacts[key]["writable_use"] = "private-staging-copy-required"
    atomic_json(destination, {
        "artifacts": artifacts, "authentication": "observed-local-provenance-only",
        "operator_specification": {"path": str(spec_path.resolve()),
                                   "sha256": sha256(spec_path)},
        "status": "PASS", "system_id": SYSTEM_ID,
    })
    destination.chmod(0o640)
    return destination


def verify_inventory(inventory: dict, host_root: Path) -> None:
    media_root = host_root / "media" / SYSTEM_ID
    for key in ("boot_floppy", "root_install_floppy"):
        item = inventory["artifacts"][key]
        path = immutable_file(Path(item["observed_path"]), media_root, item["logical_role"])
        if sha256(path) != item["sha256"] or path.stat().st_size != item["byte_size"]:
            raise UTMError(f"{item['logical_role']} no longer matches inventory")
    tape = inventory["artifacts"]["installation_tape"]
    index = immutable_file(Path(tape["index"]["observed_path"]), media_root, "tape-order-index")
    if sha256(index) != tape["index"]["sha256"]:
        raise UTMError("tape-order-index no longer matches inventory")
    for member in tape["member_order"]:
        path = immutable_file(Path(member["observed_path"]), media_root, "tape-member")
        if sha256(path) != member["sha256"] or path.stat().st_size != member["byte_size"]:
            raise UTMError(f"tape member no longer matches inventory: {member['observed_filename']}")


def verify_amix_inventory(inventory_path: Path, host_root: Path) -> None:
    try:
        inventory = json.loads(inventory_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise UTMError(f"cannot read AMIX media inventory: {exc}") from exc
    if inventory.get("system_id") != SYSTEM_ID or inventory.get("status") != "PASS":
        raise UTMError("AMIX media inventory is not a successful M4.2 inventory")
    verify_inventory(inventory, host_root)


def safe_config(text: str) -> None:
    lowered = text.lower()
    if any(value in lowered for value in FORBIDDEN):
        raise UTMError("network or public-listener setting detected in AMIX install config")
    if "@" in text:
        raise UTMError("unresolved AMIX install configuration token")


def config_text(rom: Path, key: Path | None, rdb: Path, tape: Path | None,
                boot: Path | None, root: Path | None, logs: Path) -> str:
    lines = [
        "[fs-uae]", "stdout = 1", "uaelog = 1", f"logs_dir = {logs}",
        "amiga_model = A3000", "cpu = 68030", "mmu = 68030", "fpu = 68882",
        "chip_memory = 2048", "motherboard_ram = 16384", "jit_compiler = 0",
        "network_card = 0", "bsdsocket_library = 0", f"kickstart_file = {rom}",
    ]
    if key:
        lines.append(f"kickstart_key_file = {key}")
    lines.extend([
        f"hard_drive_0 = {rdb}", "hard_drive_0_type = rdb",
        "hard_drive_0_controller = scsi6", "hard_drive_0_read_only = 0",
    ])
    if boot and root and tape:
        lines.extend([
            f"floppy_drive_0 = {boot}", f"floppy_image_0 = {boot}",
            f"floppy_image_1 = {root}",
            f"uae_uaehf1 = tape0,ro,:{tape},0,0,0,512,0,,scsi4,SCSI1",
        ])
    lines.extend(["fullscreen = 0", "window_hidden = 0", "save_states = 0", ""])
    text = "\n".join(lines)
    safe_config(text)
    return text


def prepare_amix(inventory_path: Path, workspace: Path, host_root: Path,
                 rom_path: Path, key_path: Path | None, rdb_size_mib: int) -> Path:
    staging_root = (host_root / "staging").resolve()
    destination = workspace.resolve()
    if staging_root not in destination.parents or destination.exists():
        raise UTMError("AMIX installation workspace must be a new directory beneath staging")
    if rdb_size_mib <= 0:
        raise UTMError("RDB candidate size must be a positive explicit qualification input")
    try:
        inventory = json.loads(inventory_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise UTMError(f"cannot read AMIX media inventory: {exc}") from exc
    if inventory.get("system_id") != SYSTEM_ID or inventory.get("status") != "PASS":
        raise UTMError("AMIX media inventory is not a successful M4.2 inventory")
    verify_inventory(inventory, host_root)
    media_root = host_root / "media" / SYSTEM_ID
    rom = immutable_file(rom_path, media_root, "Kickstart ROM")
    key = immutable_file(key_path, media_root, "ROM key") if key_path else None
    source_before = {
        item["observed_path"]: item["sha256"]
        for item in (inventory["artifacts"]["boot_floppy"],
                     inventory["artifacts"]["root_install_floppy"])
    }
    for member in inventory["artifacts"]["installation_tape"]["member_order"]:
        source_before[member["observed_path"]] = member["sha256"]
    tape_inventory = inventory["artifacts"]["installation_tape"]
    source_before[tape_inventory["index"]["observed_path"]] = tape_inventory["index"]["sha256"]
    source_before[str(rom)] = sha256(rom)
    if key:
        source_before[str(key)] = sha256(key)
    destination.mkdir(parents=True, mode=0o750)
    try:
        copies = {}
        for key_name, output_name in (("boot_floppy", "boot-floppy.staging"),
                                      ("root_install_floppy", "root-install-floppy.staging")):
            item = inventory["artifacts"][key_name]
            source = Path(item["observed_path"])
            output = destination / output_name
            method = copy_exclusive(source, output)
            output.chmod(0o640)
            copies[key_name] = {
                "copy_method": method, "initial_mode": "0640",
                "intended_attachment": "writable-installation-floppy",
                "output_path": str(output), "output_sha256_before_first_boot": sha256(output),
                "source_path": str(source), "source_sha256": item["sha256"],
            }
        rdb = destination / "base-amix-2.1-installation-staging.hdf"
        with rdb.open("xb") as stream:
            stream.truncate(rdb_size_mib * 1024 * 1024)
        logs = destination / "logs"; logs.mkdir(mode=0o750)
        screenshots = destination / "screenshots"; screenshots.mkdir(mode=0o750)
        tape_methods = []
        derived_index_record = None
        if tape_inventory["attachment"] == "read-only-source-directory":
            tape = Path(tape_inventory["directory"])
            tape_mode = "read-only-source-directory"
        else:
            tape = destination / "installation-tape.staging"
            tape.mkdir(mode=0o750)
            for member in tape_inventory["member_order"]:
                output = tape / member["observed_filename"]
                tape_methods.append({
                    "copy_method": copy_exclusive(Path(member["observed_path"]), output),
                    "observed_filename": member["observed_filename"],
                    "output_path": str(output),
                    "output_sha256": sha256(output),
                    "source_sha256": member["sha256"],
                })
                output.chmod(0o440)
            derived_index = tape / "index.tape"
            derived_index.write_text("\n".join(
                member["observed_filename"] for member in tape_inventory["member_order"]) + "\n")
            derived_index.chmod(0o440)
            derived_index_record = {"output_path": str(derived_index),
                                    "sha256": sha256(derived_index),
                                    "source_index": tape_inventory["index"]}
            tape_mode = "read-only-private-staging-representation"
        install_config = destination / "install.fs-uae"
        install_config.write_text(config_text(
            rom, key, rdb, tape, Path(copies["boot_floppy"]["output_path"]),
            Path(copies["root_install_floppy"]["output_path"]), logs))
        base_boot = destination / "base-first-boot.fs-uae"
        base_boot.write_text(config_text(rom, key, rdb, None, None, None, logs))
        for path, digest in source_before.items():
            if sha256(Path(path)) != digest:
                raise UTMError(f"canonical source changed during staging: {path}")
        atomic_json(destination / "install.json", {
            "base_release_target": "base AMIX 2.1 installation staging",
            "floppy_copies": copies, "golden_created": False,
            "installation_config": str(install_config),
            "inventory": str(inventory_path.resolve()),
            "patch_media_used": False,
            "rdb": {"backing_file_size": rdb.stat().st_size,
                    "candidate_input_mib": rdb_size_mib,
                    "final_geometry": "HUMAN_REQUIRED",
                    "fsuae_parameters": {"controller": "scsi6", "type": "rdb"},
                    "partition_table": "HUMAN_REQUIRED"},
            "runtime_config": str(base_boot), "serial_getty_configured": False,
            "source_hashes_before_installation": source_before,
            "status": "HUMAN_REQUIRED", "system_id": SYSTEM_ID,
            "tape_attachment": {"controller": "scsi4", "copy_methods": tape_methods,
                                "derived_index": derived_index_record,
                                "directory": str(tape), "mode": tape_mode,
                                "member_order": tape_inventory["member_order"],
                                "source_index": tape_inventory["index"]},
        })
        atomic_json(destination / "installation-evidence.json", {
            "base_release_identity": "HUMAN_REQUIRED",
            "boot_partition": "HUMAN_REQUIRED", "boot_media_success": "HUMAN_REQUIRED",
            "clean_shutdown": "HUMAN_REQUIRED", "disk_detection": "HUMAN_REQUIRED",
            "disk_devices": "HUMAN_REQUIRED", "disk_initialization": "HUMAN_REQUIRED",
            "filesystem_creation": "HUMAN_REQUIRED", "filesystem_layout": "HUMAN_REQUIRED",
            "first_hard_disk_boot": "HUMAN_REQUIRED", "installer_completion": "HUMAN_REQUIRED",
            "installer_language_and_choice": "HUMAN_REQUIRED",
            "installer_prompt_transcript": [], "kernel_system_installation": "HUMAN_REQUIRED",
            "media_detached_for_first_boot": "HUMAN_REQUIRED",
            "memory": "HUMAN_REQUIRED",
            "network_listeners": "HUMAN_REQUIRED", "package_selection": "HUMAN_REQUIRED",
            "partition_table": "HUMAN_REQUIRED", "rdb_geometry": "HUMAN_REQUIRED",
            "release_info": "HUMAN_REQUIRED", "root_floppy_transition": "HUMAN_REQUIRED",
            "source_hashes_after_installation": "HUMAN_REQUIRED",
            "tape_detection": "HUMAN_REQUIRED", "tape_reads_and_transitions": [],
        })
        return destination
    except Exception:
        # A created workspace is failure evidence; never clean it automatically.
        raise
