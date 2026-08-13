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
**COMPLETE.** Local Unix-domain PTY handoff, validated lifecycle, deterministic
admission, bounded deadlines, structured audit, preservation-safe teardown,
backend abstraction, and conservative crash reconciliation are implemented,
tested, and qualified on a Debian 13 real host with UNIX V7 under Open SIMH. No
TCP handoff was added.

The successful session, `m2-qualification-5`, recorded request, allocation,
preparation, emulator start, local attach while STARTING, `readiness_begin` on
first attach, V7 boot, `mem = 2020544`, `login:`, and STARTING -> READY ->
ACTIVE. Root login showed `rp3 on /usr`; `df` reported 1192 blocks on
`/dev/rp0` and 297416 on `/dev/rp3`. Four guest `sync` commands preceded
ACTIVE -> READY detach. The emulator PID equaled SID, PGID, and TPGID; fd 0 and
the controlling tty named the same `/dev/pts/N`; termios had `intr = ^E`,
`isig`, `-icanon`, and `-echo`.

The `--guest-synced` stop recorded Ctrl-E, a fresh monitor prompt, `quit` only
after confirmation, emulator exit, and STOPPING -> RESETTING -> RELEASED.
Supervisor diagnostics recorded, in order: `stop request accepted`,
`guest-sync attestation present`, `Ctrl-E sent`, `monitor prompt observed`,
`quit sent`, and `emulator exit observed`.

Real-host admission control refused another UNIX V7 session at the configured
per-system limit. Temporary concurrency overrides used to retain failed
evidence were removed; production defaults remain 4 total and 2 per system.
Session `m2-qualification-timeout`, run with a qualification-only short idle
deadline, recorded STARTING -> `timeout(kind=idle)` -> FAILED with `idle timeout;
emulator and workspace preserved for inspection`. It received no Ctrl-E,
`quit`, or other shutdown input and no forced kill.

Crash recovery was qualified by `m2-qualification-reconcile-2`, not by the
earlier session already FAILED through idle timeout. Before interruption it was
STARTING with supervisor PID 10329 and emulator PID 10330. After intentionally
SIGKILLing the supervisor while the emulator remained alive, reconcile reported
`failed-preserved m2-qualification-reconcile-2` and recorded FAILED
(`supervisor missing; emulator still running`) plus `result=preserved` with the
same reason. The emulator and workspace were preserved. A manual shell-variable
typo briefly referenced PID 10220; that PID is not exhibit evidence.

The final golden SHA-256 values were unchanged:

```text
root/rp0  f9f12dc7afd7bbc05c848a5d26d24a58b975c44b42e846843c01c2d1f9b4446d
usr/rp1   2e401e4c1035980ca48c93cc6834bb4b8ddd1e1f596555afa882416560ca686d
```

Historical qualification defects were resolved during M2. Buffered Open SIMH
`SET CONSOLE LOG` was replaced by process-boundary live PTY capture. Readiness
was moved from emulator launch to first attach while bounded idle/absolute
deadlines still cover abandonment. Blind Ctrl-E plus `quit` was replaced by
guest-sync attestation and a bounded monitor-confirmation handshake. PTY mode
changes alone proved insufficient: Open SIMH uses Ctrl-E as `VINTR` with
`ISIG`, signaling the controlling terminal's foreground process group. The
broker now establishes the controlling PTY/session/foreground-process-group
topology and preserves `ISIG`. These are resolved findings, not limitations.

All failed qualification sessions and workspaces remain historical evidence;
the broker does not automatically delete uncertain sessions.

Earlier attempts document how those defects were found: `unix-v7-pdp11-000001`
(PID 9058) exposed readiness timing and attach diagnostics;
`m2-qualification-2` (PID 9123) exposed the unsafe blind shutdown sequence; and
`m2-qualification-3` and `m2-qualification-4` disproved canonical/raw handling
as the full Ctrl-E solution. Their preserved state must not be presented as a
current limitation or automatically released.

## M3 — 4.3BSD / VAX
Repeatable 4.3BSD/VAX media contract, install, immutable golden, backend profile,
boot/readiness, reset, preservation checks and real-host qualification. Do not
add a BBS door or public listener in M3.

**IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION.** The manifest, external
unverified-media boundary, RA81 profiles, pinned `vax780` provisioning, broker
integration, tests, and Debian 13 procedure are present. M3 is not COMPLETE
until the two-session evidence gate in the exhibit README is performed.
`m3-qualification-1` is preserved failed evidence: 4.3BSD reached the live SIMH
monitor cleanly, but the operator entered `quit` before broker stop, producing
the correct unsolicited-exit `ACTIVE -> FAILED` result. M3 remains
**IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION** pending a fresh run.

## M4 — AMIX / Amiga 3000
FS-UAE A3000 profile, tape/media procedure, terminal handoff, reset.

## M5 — BBS door
ANSI museum menu and system cards.

## M6 — Unixish
MINIX for Atari ST, FreeMiNT on Atari TT030 or Falcon, Coherent, LUnix NG,
Plan 9.

## M7 — Beyond UNIX
VMS, TOPS-20, ITS, RT-11, RSTS/E, CP/M/MP/M.

## Planned Atari exhibits
These catalog entries remain **PLANNED** and are not assigned to M3. No
emulator qualification or bootability is established for them.

| Track | System ID | System | Canonical machine | Media availability |
|---|---|---|---|---|
| UNIX | `atari-system-v-tt030` | Atari System V / Atari UNIX | Atari TT030 / Motorola 68030 | Unverified |
| UNIX | `netbsd-atari` | NetBSD/atari | Atari TT030 or Falcon | Not established |
| UNIX | `linux-m68k-atari` | Linux/m68k on Atari | Atari TT030 or Falcon | Not established |
| Unixish | `freemint-atari` | FreeMiNT | Atari TT030 or Falcon | Not established |
| Unixish | `minix-atari-st` | MINIX for Atari ST | Atari ST | Not established |
