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

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from manifestlib import system_manifest
from utmlib import (DEFAULT_ROOT, UTMError, atomic_json, find_emulator, import_golden,
                    interactive_console, pid_alive, prepare_install, prepare_session, readiness,
                    render_runtime, safe_id, stop_process, verify_media)
from broker.config import BrokerConfig
from broker.manager import Broker


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
    for system_id in ("unix-v7-pdp11", "43bsd-vax"):
        try:
            _, manifest = system_manifest(system_id)
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
    bootstrap, runtime = prepare_install(args.system_id, Path(args.staging), root_path(args),
                                         allow_unpinned=args.allow_unpinned)
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
    runtime = {"config": str(config), "emulator": emulator,
               "session_id": session_id, "system_id": args.system_id}
    child_pid = None
    exit_code = None

    def started(pid):
        nonlocal child_pid
        child_pid = pid
        atomic_json(state, {**runtime, "pid": pid})
        print(f"RUNNING session={session_id} pid={pid}; local console attached (SIMH escape is Ctrl-E)",
              flush=True)
    try:
        exit_code = interactive_console(
            [emulator, str(config)],
            root / "sessions" / args.system_id / session_id / "console.log",
            on_start=started,
        )
        return exit_code
    finally:
        if child_pid is not None:
            atomic_json(state, {**runtime, "exit_code": exit_code, "pid": child_pid})


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


def broker_for(args):
    return Broker(root_path(args))


def print_broker_record(record):
    fields = [f"session={record.session_id}", f"system={record.system_id}",
              f"state={record.state}"]
    if record.emulator_pid: fields.append(f"emulator_pid={record.emulator_pid}")
    if record.failure: fields.append(f"failure={record.failure}")
    print(" ".join(fields))


def cmd_broker_request(args):
    record = broker_for(args).request(args.system_id, args.session_id)
    print_broker_record(record)
    print(f"Attach locally with: {sys.executable} scripts/utm.py --root {root_path(args)} broker attach {record.session_id}")
    return 0


def cmd_broker_status(args):
    print_broker_record(broker_for(args).get(args.session_id)); return 0


def cmd_broker_list(args):
    records = broker_for(args).list()
    if not records: print("(no broker sessions)")
    for record in records: print_broker_record(record)
    return 0


def cmd_broker_attach(args):
    broker_for(args).attach(args.session_id); return 0


def cmd_broker_stop(args):
    record = broker_for(args).stop(args.session_id, guest_synced=args.guest_synced,
                                   recovery=getattr(args, "recovery", False))
    print_broker_record(record)
    if record.state == "failed": print("Evidence preserved; inspect status, transcript, and audit log before release.")
    return int(record.state == "failed")


def cmd_broker_release(args):
    record = broker_for(args).release(args.session_id); print_broker_record(record); return 0


def cmd_broker_reconcile(args):
    for session_id, result in broker_for(args).reconcile(): print(f"{result:18} {session_id}")
    return 0


def cmd_broker_config(args):
    import json
    print(json.dumps(BrokerConfig.load(root_path(args)).as_dict(), sort_keys=True, indent=2)); return 0


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
    stage = install.add_parser("prepare"); stage.add_argument("system_id"); stage.add_argument("staging")
    stage.add_argument("--allow-unpinned", action="store_true")
    stage.set_defaults(func=cmd_install_prepare)
    session = sub.add_parser("session").add_subparsers(dest="session_command", required=True)
    prep = session.add_parser("prepare"); prep.add_argument("system_id"); prep.add_argument("--session-id"); prep.set_defaults(func=cmd_session_prepare)
    system = sub.add_parser("system").add_subparsers(dest="system_command", required=True)
    for name, func in (("status", cmd_system_status), ("start", cmd_system_start), ("stop", cmd_system_stop), ("ready", cmd_system_ready)):
        command = system.add_parser(name); command.add_argument("system_id"); command.add_argument("--session-id"); command.set_defaults(func=func)
        if name == "stop":
            command.add_argument("--guest-synced", action="store_true"); command.add_argument("--timeout", type=float, default=10)
        if name == "ready": command.add_argument("--timeout", type=float, default=120)
    broker = sub.add_parser("broker").add_subparsers(dest="broker_command", required=True)
    request = broker.add_parser("request"); request.add_argument("system_id")
    request.add_argument("--session-id"); request.set_defaults(func=cmd_broker_request)
    for name, func in (("status", cmd_broker_status), ("attach", cmd_broker_attach),
                       ("stop", cmd_broker_stop), ("release", cmd_broker_release)):
        command = broker.add_parser(name); command.add_argument("session_id"); command.set_defaults(func=func)
        if name == "stop":
            command.add_argument("--guest-synced", action="store_true",
                                 help="attest guest filesystems were synced; this is not an OS-shutdown claim")
    recovery = broker.add_parser("recover-stop", help="explicitly retry backend shutdown for a FAILED session")
    recovery.add_argument("session_id")
    recovery.add_argument("--guest-synced", action="store_true", required=True,
                          help="attest guest filesystems were synced; this is not an OS-shutdown claim")
    recovery.set_defaults(func=cmd_broker_stop, recovery=True)
    broker.add_parser("list").set_defaults(func=cmd_broker_list)
    broker.add_parser("reconcile").set_defaults(func=cmd_broker_reconcile)
    broker.add_parser("config").set_defaults(func=cmd_broker_config)
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
