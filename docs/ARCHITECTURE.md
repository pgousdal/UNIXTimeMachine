# Architecture

Visitor -> BBS/Telnet/SSH frontend -> Session broker -> constrained emulator adapter -> historical guest.

The first arrow and broker are future architecture, not M1 behavior. M1 is an
operator-only local console: `scripts/utm.py` validates policy and lifecycle,
then invokes the SIMH backend. It creates no listener.

The broker will own allocation, readiness, terminal handoff, timeouts, teardown, reset, and audit events. Emulator adapters remain small and declarative.

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

M1 data flow is `external media -> operator installation workspace -> read-only
golden/v7-rp06.dsk -> sessions/<system>/<session>/rp0.dsk`. The committed SIMH
template contains tokens only; the CLI resolves absolute runtime paths into a
session-local `runtime.ini`. Emulator-specific configuration stays within the
system definition and the small runtime-rendering boundary.

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
