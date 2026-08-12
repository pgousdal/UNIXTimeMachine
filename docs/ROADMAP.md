# Roadmap

## M0 — Foundation
Repository contract, taxonomy, manifests, catalog, validation, policies, provisioning skeleton.

## M1 — UNIX V7 / PDP-11
**IMPLEMENTED / AWAITING HISTORICAL-SYSTEM QUALIFICATION.** Reproducible SIMH
PDP-11/70 definition, external-media verification, immutable golden import,
disposable sessions, bounded readiness, local console lifecycle, tests, and
Debian 13 provisioning are implemented. Debian 13 provisioning, its pinned Open
SIMH build, provisioning idempotency, the executable, and host doctor after
operator enrollment have passed on the qualification VM. M1 becomes COMPLETE
only after a
real host boots a disposable session to the V7 login state, stops it, recreates
it from the golden baseline, and boots successfully a second time. Synthetic
tests and media identity verification do not satisfy that gate.

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
