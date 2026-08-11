# Architecture

Visitor -> BBS/Telnet/SSH frontend -> Session broker -> constrained emulator adapter -> historical guest.

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
