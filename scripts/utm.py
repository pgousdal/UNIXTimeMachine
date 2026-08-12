#!/usr/bin/env python3
"""UNIX Time Machine operator CLI."""
from __future__ import annotations

import argparse
import datetime as dt
import grp
import os
import pwd
import stat as statmod
import subprocess
import sys
from pathlib import Path

from manifestlib import system_manifest
from utmlib import (DEFAULT_ROOT, UTMError, atomic_json, find_emulator, import_golden,
                    pid_alive, prepare_install, prepare_session, readiness, render_runtime, safe_id,
                    stop_process, verify_media)


def root_path(args):
    return Path(args.root).resolve()


def cmd_doctor(args):
    failures = 0
    root = root_path(args)
    directory_contract = {
        "media": ("root", "unix-time-machine", 0o750),
        "golden": ("root", "unix-time-machine", 0o750),
        "state": ("unix-time-machine", "unix-time-machine", 0o2770),
        "sessions": ("unix-time-machine", "unix-time-machine", 0o2770),
        "snapshots": ("unix-time-machine", "unix-time-machine", 0o2770),
        "logs": ("unix-time-machine", "unix-time-machine", 0o2770),
        "reports": ("unix-time-machine", "unix-time-machine", 0o2770),
    }
    for directory, (owner, group, mode) in directory_contract.items():
        path = root / directory
        detail = ""
        status = "FAIL"
        try:
            stat = path.stat()
            if not statmod.S_ISDIR(stat.st_mode):
                stat = None
        except PermissionError:
            stat = None
            detail = ": permission denied"
        except OSError:
            stat = None
        if stat is not None:
            actual_owner = pwd.getpwuid(stat.st_uid).pw_name
            actual_group = grp.getgrgid(stat.st_gid).gr_name
            actual_mode = stat.st_mode & 0o7777
            if (actual_owner, actual_group, actual_mode) == (owner, group, mode):
                status = "PASS"
            else:
                detail = (f" (expected {owner}:{group} {mode:04o}; found "
                          f"{actual_owner}:{actual_group} {actual_mode:04o})")
        failures += status == "FAIL"
        print(f"{status:7} directory {path}{detail}")
    try:
        _, manifest = system_manifest("unix-v7-pdp11")
        emulator = find_emulator(manifest)
        result = subprocess.run([emulator, "-v"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=10)
        if result.returncode != 0:
            raise UTMError(f"SIMH executable is not runnable: {emulator} (exit {result.returncode})")
        print(f"PASS    SIMH executable {emulator} is runnable")
    except (ValueError, UTMError) as exc:
        failures += 1
        print(f"FAIL    {exc}")
    return int(bool(failures))


def cmd_catalog(_args):
    return subprocess.call([sys.executable, str(Path(__file__).with_name("catalog.py"))])


def cmd_media_verify(args):
    results = verify_media(args.system_id, root_path(args))
    for result in results:
        print(f"{result.status:8} {result.logical_name}: {result.detail}")
    return int(any(result.status in {"FAIL", "MISSING"} for result in results))


def cmd_golden_import(args):
    path, methods = import_golden(args.system_id, Path(args.source), root_path(args))
    print(f"PASS    imported complete prepared disk set as immutable golden ({', '.join(methods)}): {path}")
    return 0


def default_session_id():
    return "session-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def cmd_session_prepare(args):
    session_id = args.session_id or default_session_id()
    workspace, methods = prepare_session(args.system_id, session_id, root_path(args))
    print(f"PASS    session {session_id} prepared using {', '.join(methods)}: {workspace}")
    return 0


def cmd_install_prepare(args):
    bootstrap, runtime = prepare_install(args.system_id, Path(args.staging), root_path(args))
    print(f"PASS    installation bootstrap hardware staged: {bootstrap}")
    print(f"PASS    installed-system runtime verification hardware staged: {runtime}")
    print("HUMAN_REQUIRED: run the bootstrap configuration first and follow the documented guest installation and phase-transition steps")
    return 0


def selected_session(args):
    safe_id(args.system_id, "system id")
    if args.session_id:
        return safe_id(args.session_id, "session id")
    base = root_path(args) / "sessions" / args.system_id
    candidates = sorted((p.name for p in base.iterdir() if p.is_dir()), reverse=True) if base.is_dir() else []
    if not candidates:
        raise UTMError("no session exists; run session prepare first")
    return safe_id(candidates[0], "session id")


def state_path(args):
    return root_path(args) / "state" / f"{safe_id(args.system_id, 'system id')}.json"


def cmd_system_status(args):
    path = state_path(args)
    if not path.is_file():
        print("STOPPED no runtime state")
        return 0
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    alive = pid_alive(data.get("pid", -1))
    print(f"{'RUNNING' if alive else 'STOPPED'} session={data.get('session_id')} pid={data.get('pid')} config={data.get('config')}")
    return 0


def cmd_system_start(args):
    root = root_path(args)
    session_id = selected_session(args)
    _, manifest = system_manifest(args.system_id)
    emulator = find_emulator(manifest)
    config = render_runtime(args.system_id, session_id, root)
    state = state_path(args)
    if state.is_file():
        import json
        prior = json.loads(state.read_text(encoding="utf-8"))
        if pid_alive(prior.get("pid", -1)):
            raise UTMError(f"system already running as pid {prior['pid']}")
    process = subprocess.Popen([emulator, str(config)])
    atomic_json(state, {"config": str(config), "emulator": emulator, "pid": process.pid,
                        "session_id": session_id, "system_id": args.system_id})
    print(f"RUNNING session={session_id} pid={process.pid}; local console attached (SIMH escape is Ctrl-E)")
    try:
        return process.wait()
    finally:
        atomic_json(state, {"config": str(config), "emulator": emulator, "exit_code": process.poll(),
                            "pid": process.pid, "session_id": session_id, "system_id": args.system_id})


def cmd_system_stop(args):
    path = state_path(args)
    if not path.is_file():
        raise UTMError("system is not running")
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    pid = data.get("pid", -1)
    if not pid_alive(pid):
        raise UTMError(f"recorded process {pid} is not running")
    if not args.guest_synced:
        raise UTMError("refusing abrupt stop; sync the UNIX guest, halt to SIMH with Ctrl-E, and quit; use --guest-synced only after guest filesystems are synced")
    if not stop_process(pid, args.timeout):
        raise UTMError(f"SIMH did not stop within {args.timeout}s; inspect it manually (no forced kill was sent)")
    print(f"PASS    stopped SIMH pid {pid}")
    return 0


def cmd_system_ready(args):
    session_id = selected_session(args)
    _, manifest = system_manifest(args.system_id)
    log = root_path(args) / "sessions" / args.system_id / session_id / "console.log"
    status, tail = readiness(log, manifest["readiness"]["patterns"], args.timeout)
    print(f"{status} session={session_id} console={log}")
    if status != "PASS":
        print("Expected login marker was not observed within the bounded wait; inspect console.log and confirm on the local console.")
        if tail:
            print("--- console tail ---")
            print(tail[-2000:])
    return int(status != "PASS")


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=os.environ.get("UTM_ROOT", str(DEFAULT_ROOT)), help="host data root")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("catalog").set_defaults(func=cmd_catalog)
    media = sub.add_parser("media").add_subparsers(dest="media_command", required=True)
    verify = media.add_parser("verify"); verify.add_argument("system_id"); verify.set_defaults(func=cmd_media_verify)
    golden = sub.add_parser("golden").add_subparsers(dest="golden_command", required=True)
    imp = golden.add_parser("import"); imp.add_argument("system_id"); imp.add_argument("source"); imp.set_defaults(func=cmd_golden_import)
    install = sub.add_parser("install").add_subparsers(dest="install_command", required=True)
    stage = install.add_parser("prepare"); stage.add_argument("system_id"); stage.add_argument("staging"); stage.set_defaults(func=cmd_install_prepare)
    session = sub.add_parser("session").add_subparsers(dest="session_command", required=True)
    prep = session.add_parser("prepare"); prep.add_argument("system_id"); prep.add_argument("--session-id"); prep.set_defaults(func=cmd_session_prepare)
    system = sub.add_parser("system").add_subparsers(dest="system_command", required=True)
    for name, func in (("status", cmd_system_status), ("start", cmd_system_start), ("stop", cmd_system_stop), ("ready", cmd_system_ready)):
        command = system.add_parser(name); command.add_argument("system_id"); command.add_argument("--session-id"); command.set_defaults(func=func)
        if name == "stop":
            command.add_argument("--guest-synced", action="store_true"); command.add_argument("--timeout", type=float, default=10)
        if name == "ready": command.add_argument("--timeout", type=float, default=120)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except (UTMError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
