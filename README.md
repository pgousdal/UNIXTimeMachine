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
