# Roadmap

## M0 — Foundation
Repository contract, taxonomy, manifests, catalog, validation, policies, provisioning skeleton.

## M1 — UNIX V7 / PDP-11
**IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION.** Reproducible SIMH
PDP-11/70 definition, external-media verification, immutable golden import,
disposable sessions, bounded readiness, local console lifecycle, tests, and
Debian-family provisioning are implemented. M1 becomes COMPLETE only after a
real host boots a disposable session to the V7 login state, stops it, recreates
it from the golden baseline, and boots successfully a second time. Synthetic
tests and an unpinned medium do not satisfy that gate.

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
