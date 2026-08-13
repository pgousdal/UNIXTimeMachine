# UNIX Time Machine

**UNIX Time Machine** is an interactive multiuser computing museum for running authentic historical operating systems on emulated period-appropriate hardware and exposing them through terminal sessions.

Tracks: **UNIX**, **Unixish**, and **Beyond UNIX**.

## Current scope

The first milestone establishes the repository contract and three reference systems:

| System | Machine | Emulator | Track |
|---|---|---|---|
| UNIX Seventh Edition | PDP-11/70 | SIMH | UNIX |
| 4.3BSD | VAX-11/780 | SIMH | UNIX |
| Commodore Amiga UNIX 2.1 | Amiga 3000 | FS-UAE | UNIX |

See `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/PRESERVATION.md`, `docs/SECURITY.md`, and `docs/LEGAL.md`.

M1 implements the first operator-controlled exhibit: UNIX Seventh Edition on a
SIMH PDP-11/70. Its supported host baseline is Debian 13 (Trixie). It is
**COMPLETE**: two disposable real-host sessions created from the immutable
golden baseline reached the expected V7 login state, and the final golden
SHA-256 values remained unchanged. No historical media is included.

```sh
make check
python3 scripts/utm.py doctor       # expected to fail on a clean host
make provision
make operator-add USER="$USER"       # explicit enrollment; then log out/in
python3 scripts/utm.py doctor       # expected host PASS
python3 scripts/utm.py catalog
python3 scripts/utm.py media verify unix-v7-pdp11
make qualify
```

`media verify` remains `MISSING` until the operator supplies lawful historical
media; provisioning never downloads it. The exact manual installation, two-boot
qualification record, and teardown procedure is in
`systems/unix-v7-pdp11/README.md`.

M2 implements the local session-broker foundation and is **COMPLETE**. Debian 13
real-host qualification covered the normal lifecycle, admission control,
preservation-safe timeout handling, confirmed SIMH shutdown, and conservative
crash reconciliation. It allocates deterministic disposable sessions,
supervises a backend through a PTY, offers an operator-only Unix-domain console,
enforces admission and bounded deadlines, records JSON Lines audit events, and
conservatively reconciles interrupted state. It adds no network listener or BBS
integration. The qualified M1 commands remain supported.

```sh
python3 scripts/utm.py broker config
python3 scripts/utm.py broker request unix-v7-pdp11
python3 scripts/utm.py broker list
python3 scripts/utm.py broker attach SESSION_ID   # first attach starts readiness; Ctrl-] detaches
python3 scripts/utm.py broker status SESSION_ID
python3 scripts/utm.py broker stop SESSION_ID --guest-synced
python3 scripts/utm.py broker release SESSION_ID  # idempotent after automatic release
python3 scripts/utm.py broker reconcile
```

Production defaults are explicit in `broker/config.py`: 4 total sessions, 2 per
system, and startup/readiness/idle/absolute/shutdown deadlines of
10/120/1800/7200/10 seconds. An operator may override them with
`/srv/unix-time-machine/state/broker-config.json` using the exact keys printed
by `broker config`. Short deadlines and altered concurrency used during
qualification were temporary and are not recommended production settings.

UNIX V7 is operator-booted: after attach, enter `boot`, then `hp(0,0)unix`, then
Ctrl-D. The readiness deadline begins with that first successful attach, not
with emulator launch. Idle and absolute deadlines still bound an abandoned
request. Run guest `sync` commands before an explicit broker stop, then supply
`--guest-synced`. The flag attests only that filesystems were synced; it does
not claim that V7 performed a complete OS shutdown. The SIMH adapter sends
Ctrl-E, waits boundedly for a live `sim>` prompt, sends `quit` only after that
confirmation, and then waits boundedly for emulator exit. Automatic deadline
failures never inject a shutdown sequence and preserve the workspace and
emulator for inspection.

M3 implements 4.3BSD on the SIMH VAX-11/780 and is **AWAITING REAL-HOST
QUALIFICATION**. It uses the existing broker and preservation model, one RA81
disk, external unpinned operator media, operator-assisted console boot, and
4.3BSD `/etc/shutdown -h now` before the confirmed SIMH monitor handshake. See
`systems/43bsd-vax/README.md` for the contract and qualification evidence gate.
Unlike V7, 4.3BSD halt can itself reach the monitor; its profile accepts only a
fresh live-PTY `sim>` observation, then broker stop skips Ctrl-E and owns the
prompt-gated `quit`/exit path. Historical transcript text is never proof.
