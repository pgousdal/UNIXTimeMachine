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

**COMPLETE.** The manifest, external-unpinned-media boundary, RA81 install and
runtime profiles, pinned Open SIMH v3.12-3 `vax780` provisioning, broker
integration, tests, and Debian 13 real-host qualification are complete.

The installed guest booted multi-user as 4.3BSD on an 8 MiB VAX-11/780 with
`/dev/ra0a` on `/`, `/dev/ra0g` on `/mnt`, and `/dev/ra0h` on `/usr`; `df`
reported 7429, 245225, and 138584 KB respectively. The immutable golden
`rq0.dsk` SHA-256 remained
`1b8e4e73e40a4044f2eed8e13d7f1f69d1cccd6ccfb582fa6e11735f9a77aba7`.
Sessions `m3-qualification-2` and `m3-qualification-3`, each freshly copied
from that golden, passed readiness, root login, filesystem checks, clean guest
halt to a live `sim>`, broker-owned quit, exit, reset, and release. The first
also passed repeated detach/reattach. `m3-qualification-timeout` recorded
STARTING -> `timeout(kind=idle)` -> FAILED without Ctrl-E, quit, force kill, or
cleanup; its emulator and workspace were preserved.

`m3-qualification-1` also remains preserved failed evidence: its guest halt
reached the live monitor, but an operator-owned manual `quit` correctly caused
an unsolicited emulator-exit failure. This finding led to the qualified
monitor-already-active backend path. Other resolved findings were the private
writable bootstrap-miniroot staging copy and implemented-system-driven
provisioning of the VAX media directory plus shared staging root. Qualification
limits were temporary; normal production broker defaults remain in force.

## M4 — AMIX / Amiga 3000
M4 is incomplete. M4.0 establishes the conservative external-media contract
and a backend-selected console/shutdown capability boundary. M4.1 is
**COMPLETE**: Debian 13 provisioning was idempotent and the pinned FS-UAE
3.1.66 build passed the non-AMIX A3000/RDB/tape/serial substrate qualification
with run-scoped evidence and no new TCP listener. Bidirectional guest serial
traffic remains deferred until AMIX exists. M4.1 implements no FS-UAE backend,
installation, golden, or AMIX session. M4.2 is **COMPLETE**: the real
installation passed first boot, root login, read/write-root and active-swap
checks, clean shutdown, installed-HDF structure/checksum checks, generic golden
publication, and byte-identical pristine session preparation. M4.3 is
**COMPLETE**: on the Debian 13 qualification host, the canonical graphical
FS-UAE runtime booted a full-copy disposable session through `utm.py system
start` and reached the AMIX 2.1 `login:` prompt. The immutable golden was never
attached writable; runtime used only the writable session HDF and referenced
the protected operator ROM/key in their preserved filename representation.
Serial/getty readiness, patch, broker integration, and completion of the wider
M4 track remain later gates. See
`systems/amix-a3000/README.md`.

The remaining M4 work is deliberately split into narrow, independently
qualified gates:

- **M4.4 — serial/getty qualification (NEXT; PLANNED).** Configure an AMIX
  guest serial device, run `getty` on it, demonstrate bidirectional serial
  communication, and reach a real AMIX `login:` prompt over serial. This is a
  guest/emulator serial-path qualification only: it does not add broker
  integration, a generic console interface, networking, patch installation, or
  final exhibit qualification. The graphical/local display remains available
  for workstation setup, observation, qualification, and fallback.
- **M4.5 — brokered console/lifecycle integration (PLANNED).** Integrate the
  qualified AMIX serial path with the existing local UTM broker, lifecycle,
  transcript, and preservation-safe teardown model. This is the next step
  toward one console abstraction spanning SIMH and other emulator backends; it
  is not implemented by the roadmap.
- **M4.6 — official patch variant (PLANNED).** Preserve an officially patched
  AMIX installation as a documented derived variant whose parent is the
  immutable AMIX 2.1 base. It must not replace or mutate that baseline.
- **M4.7 — final AMIX exhibit qualification (PLANNED).** Qualify the complete
  AMIX exhibit from preserved inputs through disposable runtime, including its
  selected console and lifecycle behavior. M4 remains incomplete until this
  final gate is complete.

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

---

## Long-term UNIX Time Machine vision

This section is **LONG-TERM VISION**, not a claim of implemented systems or
interfaces. UNIX Time Machine should grow into a runnable preservation
environment and interactive historical UNIX museum, not merely a collection of
emulator configurations. Entries named here do not belong in the implemented
runtime catalog until they have manifests, implementation, validation, and the
appropriate qualification evidence.

### Status discipline

Roadmap and catalog work must keep these states distinct:

- **COMPLETE / qualified:** implemented and exercised against the milestone's
  stated qualification evidence.
- **Implemented; qualification pending:** code or configuration exists, but the
  required real-system or real-host evidence is incomplete.
- **PLANNED:** bounded intended work, not implemented functionality.
- **LONG-TERM VISION:** architectural direction or candidate exhibits without a
  committed implementation milestone.

A future-system list in this document must never make `utm catalog` report a
system as implemented. UNIX V7/PDP-11/70 and 4.3BSD/VAX-11/780 remain complete;
AMIX M4.1 through M4.3 remain complete according to their definitions, while
M4 overall remains incomplete.

### Preservation, variants, and lineage

The durable preservation model is:

```text
source/install media
        -> immutable original/base golden
        -> optional documented derived/patched variants
        -> disposable runtime sessions
```

Source media remain distinct from installed systems. An original/base golden
is an immutable preserved baseline and must never become an ordinary mutable
runtime disk. Runtime sessions use disposable copies. A historically meaningful
change belongs in an optional derived variant, with its transformation and
provenance documented, rather than silently changing or replacing the base.

For example:

```text
AMIX 2.1 base
        -> official patched AMIX variant
```

Long term, variant metadata should be machine-readable and identify the variant,
its parent, source inputs, derivation steps, observed hashes, and qualification
state. A derived variant is independently addressable; it does not rewrite its
lineage.

### Unified lifecycle and console architecture

The long-term operator model should converge on concepts equivalent to:

```text
catalog -> prepare -> start -> ready -> console -> stop/discard
```

These are lifecycle concepts, not a promise that commands with those names
exist. Any future CLI, museum frontend, or remote doorway must map onto the
validated broker states and preservation-safe teardown rules rather than bypass
them.

Serial or terminal access should be the preferred generic interactive interface
where historically and technically appropriate. Graphical/local display remains
necessary for workstation systems, authentic graphical exhibits, installation
and qualification, and fallback. M4.4 is the next concrete experiment; M4.5
then connects its qualified AMIX serial path to the existing broker/lifecycle
model. The intended result is a common console abstraction across SIMH and
other emulator backends without treating emulator diagnostics or a graphical
display as an authoritative serial console.

### Networking boundary

Networking remains disabled by default. Preservation, preparation, boot,
console access, shutdown, and discard must not implicitly require guest
networking or external connectivity. Future profiles may provide explicitly
selected, isolated historical networks, private virtual LANs, and tightly
controlled external access. Such profiles require their own policy,
qualification, containment, and audit treatment; they do not weaken the
offline baseline.

### Interactive historical museum

The long-term visitor experience may allow a person to browse exhibits by year,
UNIX family, or machine; launch a disposable session; connect to its appropriate
console; and safely discard it. Controlled sessions might eventually be exposed
through SSH or a BBS/login-door frontend. These visitor interfaces and remote
access paths are **LONG-TERM VISION** and do not exist merely because they are
described here.

### Historical catalog families

Candidate exhibits should be curated by lineage and historical purpose rather
than accumulated as a flat wishlist. Feasibility depends on recoverable media,
legal availability, emulator fidelity, and the ability to qualify a safe
disposable lifecycle.

- **Research UNIX:** early Research UNIX where recoverable and emulatable; V6;
  V7; 32V.
- **BSD:** early PDP-11 BSD where feasible; 4BSD, 4.2BSD, and 4.3BSD; 386BSD;
  FreeBSD; NetBSD; OpenBSD.
- **AT&T/System V:** representative System III and System V releases; SVR2,
  SVR3, and SVR4 where feasible; AMIX.
- **Commercial/workstation UNIX:** SunOS; Solaris; Ultrix; Tru64; IRIX; HP-UX;
  AIX; NeXTSTEP/OpenStep where appropriate.
- **PC UNIX:** Xenix; SCO UNIX/OpenServer; UnixWare; Interactive UNIX; Solaris
  x86 where historically useful.
- **UNIX-like, educational, and descendants:** MINIX; Coherent; historically
  significant early Linux releases and distributions. Plan 9 and Inferno are
  post-UNIX Bell Labs descendants and must be labeled as such, not presented as
  UNIX systems.

### Machine and architecture history

The museum preserves meaningful machine/OS combinations, not simply each OS on
the easiest available emulator. Primary examples include:

- UNIX V7 on PDP-11;
- 4.xBSD on VAX;
- AMIX on Amiga 3000;
- SunOS/Solaris on Sun hardware and SPARC where feasible;
- IRIX on SGI/MIPS;
- Ultrix on DEC systems; and
- NeXTSTEP on NeXT/m68k as an important primary exhibit.

Multiple ports of systems such as NetBSD, MINIX, or Debian can be separate
exhibits when the machine/OS combination itself tells a significant historical
story. Authenticity notes should distinguish primary historical combinations,
later ports, practical substitutions, and emulator limitations.

### Museum and catalog metadata

The long-term catalog model should be able to describe, without implying
qualification: year; UNIX family and lineage; OS and release; emulated machine;
architecture; emulator/backend; preservation and media status; golden or
variant identity and parentage; qualification status; console capabilities;
and networking capabilities. Museum cards can add historical significance,
suggested interactions, and authenticity notes while the machine-readable
catalog remains the authority for implemented availability and lifecycle
capabilities.
