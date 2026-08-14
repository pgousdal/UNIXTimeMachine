#!/usr/bin/env python3
"""M4.1 FS-UAE provenance and non-AMIX A3000 substrate qualification."""
from __future__ import annotations

import argparse
import json
import os
import pty
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

try:
    from .utmlib import UTMError, atomic_json, sha256
except ImportError:  # Direct execution keeps scripts/ on sys.path.
    from utmlib import UTMError, atomic_json, sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPOSITORY_ROOT / "systems/amix-a3000/m41-probe.fs-uae.in"
RUNTIME_DEPENDENCIES = (
    "libc6", "libgcc-s1", "libglib2.0-0t64", "libmpeg2-4", "libopenal1",
    "libpng16-16t64", "libsdl2-2.0-0", "libstdc++6", "libx11-6", "zlib1g",
)
FORBIDDEN_CONFIG = ("tcp://", "netplay_server", "slirp", "uae_tap", "bridge", "a2065")


def command_output(argv: list[str]) -> str:
    result = subprocess.run(argv, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=15)
    return result.stdout.strip()


def provenance(args) -> int:
    os_release = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            os_release[key] = value.strip('"')
    if os_release.get("ID") != "debian" or os_release.get("VERSION_ID") != "13":
        raise UTMError("FS-UAE provenance requires Debian 13")
    package = command_output(["dpkg-query", "-W", "-f=${Version}\t${Architecture}", "fs-uae"])
    version, architecture = package.split("\t")
    if (version, architecture) != (args.expected_version, args.expected_architecture):
        raise UTMError(f"FS-UAE package mismatch: found {version}/{architecture}")
    executable = Path("/usr/bin/fs-uae")
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise UTMError("missing or non-executable /usr/bin/fs-uae")
    version_output = command_output([str(executable), "--version"])
    if "3.1.66" not in version_output:
        raise UTMError(f"unexpected FS-UAE version output: {version_output!r}")
    dependencies = {}
    for name in RUNTIME_DEPENDENCIES:
        dependencies[name] = command_output(
            ["dpkg-query", "-W", "-f=${Version}", name])
    policy = command_output(["apt-cache", "policy", "fs-uae"])
    if args.expected_version not in policy:
        raise UTMError("pinned FS-UAE version absent from apt policy")
    report = {
        "architecture": architecture,
        "apt_policy": policy.splitlines(),
        "deb_filename": args.deb_filename,
        "deb_sha256": args.deb_sha256,
        "debian_release": os_release.get("PRETTY_NAME"),
        "dependencies": dependencies,
        "executable": str(executable),
        "executable_sha256": sha256(executable),
        "fs_uae_version_output": version_output,
        "package": "fs-uae",
        "package_origin": "Debian archive",
        "package_version": version,
        "repository_component": args.component,
        "repository_suite": args.suite,
    }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


def immutable_external(path: Path, media_root: Path, label: str) -> dict[str, object]:
    try:
        resolved = path.resolve(strict=True)
        root = media_root.resolve(strict=True)
        info = resolved.stat()
    except OSError as exc:
        raise UTMError(f"{label} missing or inaccessible: {exc}") from exc
    if root not in resolved.parents or not stat.S_ISREG(info.st_mode):
        raise UTMError(f"{label} must be a regular file beneath {root}")
    if info.st_mode & 0o222:
        raise UTMError(f"{label} source must have no write bits: {resolved}")
    return {"path": str(resolved), "size": info.st_size, "sha256": sha256(resolved),
            "authenticity": "UNPINNED"}


def new_workspace(path: Path, root: Path) -> Path:
    workspace = path.resolve()
    staging = (root / "staging").resolve()
    if staging not in workspace.parents or workspace.exists():
        raise UTMError("probe workspace must be a new directory beneath staging")
    workspace.mkdir(parents=True, mode=0o750)
    return workspace


def render_probe(workspace: Path, rom: Path, rom_key: Path | None, serial_pty: str) -> Path:
    values = {
        "@ROM@": str(rom.resolve()),
        "@ROM_KEY_OPTION@": (f"kickstart_key_file = {rom_key.resolve()}"
                            if rom_key else ""),
        "@RDB@": str((workspace / "probe-rdb.hdf").resolve()),
        "@SERIAL_PTY@": serial_pty,
        "@TAPE_DIR@": str((workspace / "probe-tape").resolve()),
    }
    text = TEMPLATE.read_text()
    for token, value in values.items():
        text = text.replace(token, value)
    unresolved = text.replace("@QUALIFICATION_PTY@", "").replace(
        "@QUALIFICATION_LOG_DIR@", "")
    if "@" in unresolved:
        raise UTMError("unresolved M4.1 configuration token")
    lowered = text.lower()
    if any(value in lowered for value in FORBIDDEN_CONFIG):
        raise UTMError("network or TCP setting detected in M4.1 configuration")
    config = workspace / "m41-probe.fs-uae"
    config.write_text(text)
    return config


def prepare(args) -> int:
    root = Path(args.root).resolve()
    media_root = root / "media/amix-a3000"
    rom_path = Path(args.rom)
    observed = {"rom": immutable_external(rom_path, media_root, "Kickstart ROM")}
    if args.rom_key:
        observed["rom_key"] = immutable_external(Path(args.rom_key), media_root, "ROM key")
    workspace = new_workspace(Path(args.workspace), root)
    rdb = workspace / "probe-rdb.hdf"
    with rdb.open("xb") as stream:
        stream.truncate(args.rdb_size_mib * 1024 * 1024)
    tape = workspace / "probe-tape"
    tape.mkdir(mode=0o750)
    member = tape / "probe-member.bin"
    member.write_bytes(b"UNIX Time Machine synthetic M4.1 tape capability probe\n")
    member.chmod(0o440)
    (tape / "index.tape").write_text(member.name + "\n")
    (tape / "index.tape").chmod(0o440)
    config = render_probe(workspace, rom_path,
                          Path(args.rom_key) if args.rom_key else None,
                          "@QUALIFICATION_PTY@")
    atomic_json(workspace / "probe.json", {
        "artifacts": observed, "config": str(config), "probe_rdb": str(rdb),
        "probe_rdb_size": rdb.stat().st_size, "synthetic_tape": str(tape),
        "status": "HUMAN_REQUIRED", "system_id": "amix-a3000",
    })
    print(f"PASS    prepared non-AMIX probe workspace: {workspace}")
    print(f"PASS    ROM observed as UNPINNED immutable external media: {observed['rom']['sha256']}")
    print("HUMAN_REQUIRED: run qualify on the Debian 13 host with an available local display")
    return 0


def listening_tcp() -> set[str]:
    result = subprocess.run(["ss", "-H", "-ltn"], check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    return set(result.stdout.splitlines())


def runtime_evidence(text: str, metadata: dict, slave_path: str) -> dict[str, bool]:
    """Evaluate only detailed UAE output produced by the current run."""
    rdb = re.escape(str(Path(metadata["probe_rdb"]).resolve()))
    tape = re.escape(str(Path(metadata["synthetic_tape"]).resolve()))
    index = re.escape(str((Path(metadata["synthetic_tape"]) / "index.tape").resolve()))
    serial = re.escape(slave_path)
    rdb_kib = metadata["probe_rdb_size"] // 1024
    checks = {
        "a3000": r'config match for ["\']A3000["\']',
        "cpu_fpu_mmu_jit": r"CPU=68030,\s*FPU=68882,\s*MMU=68030,\s*JIT(?:=[^=,\s]+)?=0",
        "chip_ram_2_mib": (r"(?:\bchipmem_size\s*[=:]\s*4\b|"
                           r"set option [\"']chipmem_size[\"'] to [\"']4[\"'])"),
        "a3000_ram_16_mib": (r"(?:\ba3000mem_size\s*[=:]\s*16\b|"
                                r"set option [\"']a3000mem_size[\"'] to [\"']16[\"'])"),
        "a3000_scsi": r"Initializing A3000 mainboard SCSI",
        "rdb_hd_unit_6": rf"Adding A3000 mainboard SCSI HD unit 6 .*{rdb}",
        "rdb_opened": rf"HDF opened as {rdb_kib}K\b",
        "tape_unit_4": rf"Adding A3000 mainboard SCSI TAPE unit 4 .*{tape}",
        "tape_index_opened": rf"TAPEEMU INDEX:\s*['\"]?{index}['\"]?",
        "serial_device": rf"serial port device:\s*{serial}",
        "serial_opened": rf"serial:\s*open ['\"]{serial}['\"]\s*->\s*fd=\d+",
        "clean_shutdown": r"SDL_QUIT",
    }
    evidence = {name: re.search(pattern, text, re.IGNORECASE) is not None
                for name, pattern in checks.items()}
    rom = re.escape(str(Path(metadata["artifacts"]["rom"]["path"]).resolve()))
    evidence["rom_loaded"] = re.search(
        rf"(?:Known|Unknown) ROM ['\"]{rom}['\"] loaded", text, re.IGNORECASE) is not None
    evidence["rom_identity_unknown"] = re.search(
        rf"Unknown ROM ['\"]{rom}['\"] loaded", text, re.IGNORECASE) is not None
    if "rom_key" in metadata["artifacts"]:
        evidence["encrypted_rom_key_loaded"] = re.search(
            r"read rom key file, size\s*=\s*\d+", text, re.IGNORECASE) is not None
        evidence["encrypted_rom_decoded_loaded"] = (
            evidence["encrypted_rom_key_loaded"] and
            evidence["rom_loaded"])
    return evidence


def validate_run_log(log_path: Path, run_started_ns: int, metadata: dict,
                     slave_path: str) -> tuple[dict[str, bool], list[str]]:
    if not log_path.is_file():
        raise UTMError("current run did not create its detailed UAE log")
    if log_path.stat().st_mtime_ns < run_started_ns:
        raise UTMError("detailed UAE log predates the current run boundary")
    evidence = runtime_evidence(log_path.read_text(errors="replace"), metadata, slave_path)
    informational = {"rom_identity_unknown", "encrypted_rom_key_loaded"}
    missing = [name for name, present in evidence.items()
               if not present and name not in informational]
    return evidence, missing


def qualify(args) -> int:
    workspace = Path(args.workspace).resolve(strict=True)
    metadata = json.loads((workspace / "probe.json").read_text())
    if metadata.get("status") != "HUMAN_REQUIRED":
        raise UTMError("invalid or already reconciled M4.1 probe metadata")
    if not os.environ.get("DISPLAY"):
        print("HUMAN_REQUIRED: no local DISPLAY is available; do not claim startup qualification")
        return 2
    master, slave = pty.openpty()
    process = None
    run_dir = workspace / "runs" / f"run-{time.time_ns()}-{os.getpid()}"
    run_dir.mkdir(parents=True, mode=0o750)
    stdout_log = run_dir / "fs-uae-stdout.log"
    stderr_log = run_dir / "fs-uae-stderr.log"
    detailed_log = run_dir / "fs-uae.log.txt"
    results_path = run_dir / "qualification.json"
    try:
        slave_path = os.ttyname(slave)
        template = (workspace / "m41-probe.fs-uae").read_text()
        config = run_dir / "m41-qualified.fs-uae"
        config.write_text(template.replace("@QUALIFICATION_PTY@", slave_path).replace(
            "@QUALIFICATION_LOG_DIR@", str(run_dir)))
        before = listening_tcp()
        with stdout_log.open("wb") as stdout, stderr_log.open("wb") as stderr:
            run_started_ns = time.time_ns()
            process = subprocess.Popen(["/usr/bin/fs-uae", str(config)],
                                       stdin=subprocess.DEVNULL, stdout=stdout,
                                       stderr=stderr)
            time.sleep(args.observe_seconds)
            if process.poll() is not None:
                raise UTMError(
                    f"FS-UAE exited during startup ({process.returncode}); evidence preserved")
            after = listening_tcp()
            if after - before:
                raise UTMError(f"unexpected TCP listener(s): {sorted(after - before)}")
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired as exc:
                raise UTMError(
                    "FS-UAE controlled exit timed out; process left for inspection") from exc
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        os.close(master)
        os.close(slave)
    evidence, missing = validate_run_log(
        detailed_log, run_started_ns, metadata, slave_path)
    diagnostic_text = stdout_log.read_text(errors="replace") + "\n" + (
        stderr_log.read_text(errors="replace"))
    network_warning = "Unrecognized network card" in diagnostic_text or (
        "Unrecognized network card" in detailed_log.read_text(errors="replace"))
    if network_warning:
        missing.append("network_card_disabled_without_warning")
    results = {
        "configuration_accepted": not network_warning,
        "controlled_exit_code": process.returncode,
        "detailed_uae_log": str(detailed_log),
        "display": os.environ["DISPLAY"],
        "display_classification": "observed-local-display-candidate",
        "runtime_evidence": evidence,
        "rom_identity": "Unknown ROM" if evidence["rom_identity_unknown"] else "not-asserted",
        "new_tcp_listeners": [],
        "run_directory": str(run_dir),
        "run_started_ns": run_started_ns,
        "serial_pty": slave_path,
        "stderr_log": str(stderr_log),
        "stdout_log": str(stdout_log),
        "topology_evidence_missing": missing,
    }
    atomic_json(results_path, results)
    if missing:
        raise UTMError(f"FS-UAE topology evidence incomplete: {', '.join(missing)}")
    print("PASS    FS-UAE started with the non-AMIX A3000 substrate")
    print("PASS    no new TCP listener was observed")
    print("SKIP    bidirectional serial bytes require a guest serial driver; deferred without AMIX")
    print("HUMAN_REQUIRED: review native display and diagnostics before reconciling M4.1")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)
    p = commands.add_parser("provenance")
    p.add_argument("--expected-version", required=True); p.add_argument("--expected-architecture", required=True)
    p.add_argument("--suite", required=True); p.add_argument("--component", required=True)
    p.add_argument("--deb-filename", required=True); p.add_argument("--deb-sha256", required=True)
    p.set_defaults(function=provenance)
    p = commands.add_parser("prepare")
    p.add_argument("--root", default="/srv/unix-time-machine"); p.add_argument("--workspace", required=True)
    p.add_argument("--rom", required=True); p.add_argument("--rom-key"); p.add_argument("--rdb-size-mib", type=int, default=64)
    p.set_defaults(function=prepare)
    p = commands.add_parser("qualify")
    p.add_argument("--workspace", required=True); p.add_argument("--observe-seconds", type=int, default=5)
    p.set_defaults(function=qualify)
    return result


def main(argv=None) -> int:
    try:
        args = parser().parse_args(argv)
        return args.function(args)
    except (OSError, subprocess.SubprocessError, UTMError, ValueError) as exc:
        print(f"FAIL    {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
