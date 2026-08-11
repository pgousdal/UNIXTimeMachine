#!/usr/bin/env bash
set -euo pipefail
ROOT="${UTM_ROOT:-/srv/unix-time-machine}"
if [[ "$EUID" -ne 0 ]]; then echo "Run as root: sudo $0" >&2; exit 1; fi
install -d -m 0755 "$ROOT"/{media,golden,state,sessions,snapshots,logs,reports}
echo "Created UNIX Time Machine host layout at $ROOT"
