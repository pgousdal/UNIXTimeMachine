# UNIX V7 / PDP-11/70 (M1)

Status: **IMPLEMENTED / AWAITING REAL-HOST REQUALIFICATION**.

## Machine definition and assumptions

The exhibit is a DEC PDP-11/70 with 2 MiB of memory, an RH70-class MASSBUS
controller, and one RP06 disk at SIMH `RP0`. It boots `RP0`. The console is the
local DL11 console recorded to the session's `console.log`; no SIMH Telnet or
network listener is configured. XQ/XU guest Ethernet and extra terminal
multiplexers are disabled. A 60 Hz line clock matches North American period
hardware and the V7 installation convention used by the primary procedure.

These choices follow the Open SIMH PDP-11 simulator documentation and the Open
SIMH *Installing and Using Research Unix Version 7* guide, whose normal-boot
profile uses an 11/70, 2 MiB, RP06, and direct RP boot. `set cpu idle` is an
emulator host-efficiency decision, not additional guest hardware. Debian 13 has
no official `simh` package: it was removed from testing before Trixie released.
Provisioning therefore builds Open SIMH's signed v3.12-3 tag at full commit
`9d2bbe7c3271cfe57400ba9e8e3679f9f6b5944d`; the upstream archive SHA-256 is
`0cc28f8fee3348dca3c42ab5406393ad1e78a7716085fcc24d7ddfb189082481`.
Only `pdp11` is built, with `NONETWORK=1`, and installed at
`/opt/unix-time-machine/simh/v3.12-3/pdp11`. References:

- https://opensimh.org/simdocs/pdp11_doc.html
- https://opensimh.org/research-unix-7-pdp11-45-v2.0.pdf
- https://github.com/open-simh/simh/tree/v3.12-3
- https://packages.debian.org/search?keywords=simh
- https://tracker.debian.org/news/1553687/simh-removed-from-testing/

The media manifest accepts `v7.tap` or `unix-v7.tap` as operator conventions.
Its size and SHA-256 are deliberately unpinned: no canonical identity has yet
been established. `UNPINNED` is therefore not authenticity verification.

## Exact operator procedure

Commands assume the repository root and an operator able to write the provisioned
directories (for example via the `unix-time-machine` group).

### A. Provision the host

```sh
sudo apt-get install ansible
make check
python3 scripts/utm.py doctor       # clean-host failures are expected
make provision
python3 scripts/utm.py doctor       # all host checks must pass
python3 scripts/utm.py catalog
python3 scripts/utm.py media verify unix-v7-pdp11
make qualify
```

Log out/in after adding an operator to the service group if needed. Do not run
SIMH as an untrusted user. `make qualify` combines repository checks, host
doctor, honest media verification, and a reminder for manual boots; these gates
remain distinct. Missing historical media is expected until section B and is
not repaired by provisioning.

### B. Place legally obtained media

After determining that you may use it, use an administrator-controlled copy to
place exactly one accepted tape filename in
`/srv/unix-time-machine/media/unix-v7-pdp11/`. Do not copy it into Git.

### C. Verify media

```sh
python3 scripts/utm.py media verify unix-v7-pdp11
```

Expected today is `UNPINNED` plus the observed SHA-256. Record that hash, source,
acquisition date, and provenance externally. `MISSING`/`FAIL` stops the workflow.

### D. Prepare/install the golden system — HUMAN_REQUIRED

The repository does **not** automate the licensed UNIX V7 installation and does
not claim the accepted tape layout matches every lawful distribution. Follow the
installation instructions accompanying your medium, using Open SIMH's cited V7
guide as a technical reference. Work on a new RP06 image in an operator staging
directory outside `media/`, not on the tape and not in `golden/`. Configure the
same PDP-11/70, 2 MiB, RP06 geometry, and no networking. Complete installation,
write the RP boot block, boot it, check filesystems, and run `sync` repeatedly
before stopping SIMH. Keep all installer-specific configuration outside Git if it
contains media paths.

Import the *installed disk*, never the source tape:

```sh
sudo python3 scripts/utm.py golden import unix-v7-pdp11 /path/to/staging/v7-rp06.dsk
```

This is exclusive and refuses overwrite. Replacing a golden image requires a
separate, explicit operator archival/removal decision outside this CLI.

### E. Validate the golden system — HUMAN_REQUIRED

Retain provenance and the `golden_sha256` written in `golden/.../metadata.json`.
Confirm the staging installation booted and was cleanly synced. The golden file
is mode 0440 and must never be attached to SIMH.

### F. Create a disposable session

```sh
python3 scripts/utm.py session prepare unix-v7-pdp11 --session-id qualification-1
```

### G. Boot the session

In the local operator terminal:

```sh
python3 scripts/utm.py system start unix-v7-pdp11 --session-id qualification-1
```

V7 may first present its boot prompt; follow the installed system's documented
boot input (commonly `boot` followed by `hp(0,0)unix`). This interaction cannot
yet be generalized safely by the CLI.

### H. Verify console/login

In another terminal, use the bounded detector:

```sh
python3 scripts/utm.py system ready unix-v7-pdp11 --session-id qualification-1 --timeout 120
```

`PASS` means the configured `login:` marker appeared in the console log. A timeout
is `HUMAN_REQUIRED`, never a synthetic pass; inspect `console.log` and the live
console. Record the observed banner/login state and SIMH version in an external
qualification report without passwords.

### I. Stop and discard the session

Inside V7 as an authorized operator run `sync` several times. Press Ctrl-E for
the SIMH prompt, then `quit`. Alternatively, only after syncing, another terminal
may run `system stop ... --guest-synced`; it sends SIGINT, waits boundedly, and
never force-kills. Confirm `system status` reports stopped. Then archive logs as
needed and explicitly remove only the named session directory; M1 provides no
destructive discard command.

### J. Demonstrate reproducibility — HUMAN_REQUIRED

Create `qualification-2`, repeat F–I from the unchanged golden disk, and compare
the recorded golden hash. Only two successful real-host boots to the expected V7
login state, with clean stops and a freshly recreated second session, permit M1
to be marked COMPLETE.

```sh
python3 scripts/utm.py session prepare unix-v7-pdp11 --session-id qualification-2
python3 scripts/utm.py system start unix-v7-pdp11 --session-id qualification-2
```
