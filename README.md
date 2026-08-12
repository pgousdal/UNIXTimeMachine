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

M2 implements the local session-broker foundation and is **IMPLEMENTED / AWAITING
REAL-HOST QUALIFICATION**. It allocates deterministic disposable sessions,
supervises a backend through a PTY, offers an operator-only Unix-domain console,
enforces admission and bounded deadlines, records JSON Lines audit events, and
conservatively reconciles interrupted state. It adds no network listener or BBS
integration. The qualified M1 commands remain supported.

```sh
python3 scripts/utm.py broker config
python3 scripts/utm.py broker request unix-v7-pdp11
python3 scripts/utm.py broker list
python3 scripts/utm.py broker attach SESSION_ID   # Ctrl-] detach; Ctrl-E reaches SIMH
python3 scripts/utm.py broker status SESSION_ID
python3 scripts/utm.py broker stop SESSION_ID     # sync the guest first
python3 scripts/utm.py broker release SESSION_ID  # idempotent after automatic release
python3 scripts/utm.py broker reconcile
```

Defaults are explicit in `broker/config.py`; an operator may override them with
`/srv/unix-time-machine/state/broker-config.json` using the exact keys printed
by `broker config`. M2 must not be marked complete until the real-host gate in
`docs/ROADMAP.md` has been observed.
