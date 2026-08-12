# Roadmap

## M0 — Foundation
Repository contract, taxonomy, manifests, catalog, validation, policies, provisioning skeleton.

## M1 — UNIX V7 / PDP-11
**COMPLETE.** Reproducible SIMH
PDP-11/70 definition, external-media verification, immutable golden import,
disposable sessions, bounded readiness, local console lifecycle, tests, and
Debian 13 provisioning are implemented. Debian 13 provisioning, its pinned Open
SIMH build, provisioning idempotency, the executable, and host doctor after
operator enrollment passed on the qualification VM. Two fresh disposable
real-host sessions from the same immutable golden baseline reached the expected
V7 login state; the second verified the PDP-11/70 memory, root login, `/usr`
mount, disk availability, clean stop, and unchanged golden hashes. The Open
SIMH live-console logging defect found during qualification was resolved by
capturing the PTY stream outside the emulator.

## M2 — Session broker
PTY/TCP handoff, timeouts, admission, audit, teardown.

## M3 — 4.3BSD / VAX
Repeatable boot and reset.

## M4 — AMIX / Amiga 3000
FS-UAE A3000 profile, tape/media procedure, terminal handoff, reset.

## M5 — BBS door
ANSI museum menu and system cards.

## M6 — Unixish
MINIX, Coherent, LUnix NG, Plan 9.

## M7 — Beyond UNIX
VMS, TOPS-20, ITS, RT-11, RSTS/E, CP/M/MP/M.
