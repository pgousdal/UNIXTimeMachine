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
**IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION.** Local Unix-domain PTY
handoff, validated lifecycle, deterministic admission, bounded startup,
readiness/idle/absolute/shutdown deadlines, structured audit, preservation-safe
teardown, backend abstraction and conservative crash reconciliation are
implemented and covered by synthetic tests. No TCP handoff was added.

M2 becomes **COMPLETE** only after a Debian 13 qualification demonstrates with
the real UNIX V7 backend: allocation, complete preparation, emulator start,
readiness, attach, ACTIVE, clean detach, guest-synced stop, reset/discard,
release, unchanged golden hashes, timeout handling, and reconciliation after an
intentionally interrupted supervisor. Record commands, session IDs, audit
events and before/after golden hashes; unit tests alone do not close this gate.

The first real-host attempt (`unix-v7-pdp11-000001`, Open SIMH PID 9058)
manually reached `mem = 2020544` and `login:`, but exposed a lifecycle defect:
readiness had been timed from emulator launch and expired before operator boot.
The timeout then attempted an unconfirmed shutdown; the emulator was correctly
left running, while its vanished socket also exposed an uncontrolled attach
traceback. M2 remains **IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION** after
the correction: startup covers transport creation, first attach begins the
interactive readiness interval, abandoned STARTING is bounded by idle/absolute
expiry, and automatic expiry preserves without shutdown input. The preserved
session is qualification evidence, not disposable state for automatic deletion.

The second attempt (`m2-qualification-2`, preserved emulator PID 9123) proved
the complete operator-assisted boot/readiness and repeated attach lifecycle,
including V7 root login, 2 MiB memory, `/usr` on `rp3`, and four guest `sync`
commands. Its stop exposed a second defect: the supervisor wrote Ctrl-E and
`quit` together, so V7 consumed `quit` before SIMH monitor entry was confirmed.
The corrected M2 requires explicit `--guest-synced` attestation, performs a
bounded Ctrl-E / observed `sim>` / `quit` / observed-exit handshake, records
control-plane diagnostics, and refuses ordinary stop from FAILED. Both failed
real-host sessions remain preserved evidence. M2 is still **IMPLEMENTED /
AWAITING REAL-HOST QUALIFICATION**.

The third real-host attempt (`m2-qualification-3`) passed V7 boot/readiness,
attach/detach, memory (`2020544`), `/usr` on `rp3`, four guest syncs, and
golden-hash preservation, but shutdown timed out after Ctrl-E because the
child PTY slave was left in canonical mode. A standalone escape byte could be
held by the line discipline, so no fresh `sim>` was observed. The supervisor
now configures the slave raw/noncanonical before exec; the confirmed
Ctrl-E / fresh `sim>` / `quit` / exit handshake remains mandatory. Preserve
this failed session and workspace as qualification evidence; do not discard or
reuse them during qualification-4.

## M3 — 4.3BSD / VAX
Repeatable 4.3BSD/VAX media contract, install, immutable golden, backend profile,
boot/readiness, reset, preservation checks and real-host qualification. Do not
add a BBS door or public listener in M3.

## M4 — AMIX / Amiga 3000
FS-UAE A3000 profile, tape/media procedure, terminal handoff, reset.

## M5 — BBS door
ANSI museum menu and system cards.

## M6 — Unixish
MINIX, Coherent, LUnix NG, Plan 9.

## M7 — Beyond UNIX
VMS, TOPS-20, ITS, RT-11, RSTS/E, CP/M/MP/M.
