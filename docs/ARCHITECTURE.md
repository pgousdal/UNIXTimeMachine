# Architecture

Future visitor frontend -> session broker -> constrained emulator adapter -> historical guest.

The first arrow remains future architecture. M1 is an
operator-only local console: `scripts/utm.py` validates policy and lifecycle,
then invokes the SIMH backend. It creates no listener.

M2's broker owns allocation, readiness, terminal handoff, timeouts, teardown,
reset and audit events. `Backend` is the emulator-neutral contract;
`SimhBackend` adapts the qualified M1 preparation/runtime primitives. Later
FS-UAE, QEMU, MAME and specialist adapters implement that contract rather than
adding emulator rules to the broker.

The validated lifecycle is:

```text
REQUESTED -> ALLOCATED -> PREPARING -> STARTING -> READY <-> ACTIVE
                                                    |          |
                                                    +-> STOPPING -> RESETTING -> RELEASED
Any pre-release operational state -> FAILED; FAILED -> STOPPING or RESETTING.
```

Every edge is checked. Records under `state/broker/sessions/` are deterministic
JSON written by atomic replace under a broker file lock. Allocation uses an
atomically persisted monotonic counter and refuses any state-record or workspace
collision. `logs/broker-audit.jsonl` uses one `O_APPEND` write per structured
event. Console bytes are stored separately under `logs/sessions/SESSION_ID/`.

Each session has a detached supervisor which owns the emulator PTY, live
transcript and a mode-0660 Unix-domain socket under `state/broker/`. `attach`
relays the local terminal; Ctrl-E is transparent to SIMH and Ctrl-] is the local
detach escape. Only one attachment is allowed. No TCP socket is created.

Admission counts every non-released record, including FAILED evidence, and
applies total and per-system limits. Startup, readiness, idle, absolute runtime and shutdown all
have positive finite deadlines. On stop/timeout the adapter's safe monitor-exit
sequence is attempted. A confirmed exit advances through reset and automatically
removes only the session workspace; records, audit and diagnostics remain. An
unconfirmed exit becomes FAILED and its workspace is preserved.
The supervisor and local PTY remain available in that case so an operator can
inspect, attach, clean up and retry a bounded stop; no forced kill is sent.

PID records include Linux `/proc` start ticks so a recycled PID is never treated
as the original process. `broker reconcile` marks records with missing/mismatched
supervisors FAILED, reports whether an emulator still matches, and preserves
orphan preparation directories. It never deletes uncertain state.

Canonical host layout:

```text
/srv/unix-time-machine/
├── media/
├── golden/
├── state/
├── sessions/
├── snapshots/
├── logs/
└── reports/
```

M1 data flow is `external media -> operator staging disk set -> atomic read-only
golden disk set -> complete disposable session disk set`. UNIX V7 has two RP06
members: RP0 (root and swap) and RP1 (`/usr`). The manifest's ordered
`prepared.disks` structure is system-neutral and records each unit, device,
golden/session filename, and runtime token. Golden import constructs the whole
set in a sibling transaction directory, hashes every member, and publishes it
with one rename. Before publication, the complete tree is set to root ownership,
the `unix-time-machine` operator group, mode 0750 on its directory, and mode 0440
on disks and metadata. Session preparation remains unprivileged, rejects
incomplete sets, and copies every member before publishing session metadata.
The committed SIMH templates contain tokens only; the CLI resolves session-local
absolute paths.

Persistent JSON is deterministic and atomically replaced. A foreground SIMH
process retains the local terminal; PID/config/session metadata enables status
and a conservative stop command from another operator terminal.

The M1 emulator supply chain is separate from historical media. On Debian 13,
Ansible retrieves the SHA-256-pinned archive for Open SIMH v3.12-3 commit
`9d2bbe7c3271cfe57400ba9e8e3679f9f6b5944d`, builds only the network-disabled
PDP-11 target, and installs `/opt/unix-time-machine/simh/v3.12-3/pdp11`.
Runtime selection is this absolute manifest path, never ambient `PATH`. The
source archive is retained in a controlled cache; the transient source/build
tree is removed.
