# UNIX V7 / PDP-11/70 (M1)

Status: **IMPLEMENTED / AWAITING HISTORICAL-SYSTEM QUALIFICATION**.

## Canonical definition

The runtime is a PDP-11/70 with 2 MiB, an RH70-class MASSBUS attachment as
represented by Open SIMH's `RP` device, and two RP06 units. RP0 contains V7 root
on `hp(0,0)` and swap on its partition 1. RP1 contains `/usr` on its partition 7;
the restored V7 name for that device is `/dev/rp3` (block major 6, minor 15),
despite the host emulator unit being RP1. Boot is from RP0, followed at the boot
prompt by `hp(0,0)unix`. Both disks remain required at runtime.

This is Model B. It matches the cited Open SIMH installation: its initial
PDP-11/45 uses two RP06 disks, restores the root dump to RP0 and the `/usr` dump
to RP1, and keeps both disks attached when upgrading normal operation to an
11/70 with 2 MiB. A single RP06 has unused partitions and could be repartitioned
or populated differently, but that would be a different installation recipe;
it is not the conservative, directly documented result preserved by M1.

The console is local and logged. XQ, XU, DZ and other network/listener-capable
devices are disabled. Open SIMH v3.12-3 is built with `NONETWORK=1`. `RH70` in
the manifest describes the period controller class; Open SIMH exposes the
RP04/05/06 controller/drives collectively as `RP`, while V7 calls these disks
`hp` in standalone boot syntax and its device driver.

Authoritative and project sources:

- TUHS archive path: `Archive/Distributions/Research/Keith_Bostic_v7/`
  (`f0.gz` through `f6.gz`, `filelist`, tape builders, and `v7.tap.gz`).
- TUHS archive description says the Keith Bostic files look like original tape
  records. That is provenance evidence, not proof of an untouched original tape.
- TUHS, *Setting Up UNIX — Seventh Edition*:
  https://www.tuhs.org/Archive/Distributions/Research/Documentation/v7_setup.html
- Open SIMH, *Installing and Using Research Unix Version 7*, current 3.2 guide:
  https://decuser.github.io/assets/pdf/unix/research-unix-7-pdp11-45-3.2.pdf
- Open SIMH PDP-11 simulator documentation:
  https://opensimh.org/simdocs/pdp11_doc.html
- Pinned emulator: https://github.com/open-simh/simh/tree/v3.12-3

## Installation-tape identity

M1 supports one canonical installation bitstream: the decompressed content of
TUHS `Keith_Bostic_v7/v7.tap.gz` as published after the May 2024 tape-builder
correction that added the logical end-of-tape/physical end marker. The current
Open SIMH guide documents the seven source records and SHA-1, and independently
rebuilding/downloading the TUHS artifact establishes this identity:

```text
size     11711508 bytes
SHA-1    8056d35a2cb6529330f26db5754e858c9eab0462  (secondary identifier)
SHA-256  e2a6c5d420e2db62e992a95fce420bf311c3afa89b38381b8d212c92eef5a6cf
```

The SHA-256 was computed directly over the decompressed TUHS artifact; it was
not inferred from SHA-1. Earlier generated copies (including a documented older
builder SHA-1), Henry Spencer content archives, Nijmegen/Torsten media, and
other legitimate V7 layouts are not byte-equivalent merely because they are V7
or named `v7.tap`. M1 deliberately verifies only this one exact bitstream.
`MISSING` means absent; wrong size/hash or multiple accepted filenames is
`FAIL`. Adding another variant requires its own explicit identity and install
contract, not another ambiguous filename.

This digest establishes bitstream identity only. It does not establish legal
permission to acquire, possess, use, or redistribute UNIX. Media remains
external and provisioning, CI and tests never download it.

## Operator and host preparation

From the repository root on Debian 13:

```sh
make check
make provision
make operator-add USER="$USER"
```

Log out completely and log in again so the new `unix-time-machine` supplementary
group becomes effective. Enrollment is explicit and idempotent; provisioning
does not grant arbitrary local users access. Then run:

```sh
python3 scripts/utm.py doctor
python3 scripts/utm.py media verify unix-v7-pdp11
```

Doctor is read-only. The already-present external tape must report `PASS`.

## Create the two staging disks — HUMAN_REQUIRED

Choose a new staging directory outside `/srv/unix-time-machine/media` and
`/srv/unix-time-machine/golden`; it must not already exist:

```sh
STAGING=/srv/unix-time-machine/sessions/install-unix-v7-pdp11
python3 scripts/utm.py install prepare unix-v7-pdp11 "$STAGING"
/opt/unix-time-machine/simh/v3.12-3/pdp11 "$STAGING/install.ini"
```

The helper creates only the hardware configuration and directory. SIMH creates
`rp0.dsk` and `rp1.dsk` on first attachment. It attaches the verified external
`v7.tap` with `attach -r`, logs the console, disables networking, and boots TM0.
Answer `y` to SIMH's “Overwrite last track?” prompt for both newly created RP06
staging disks. Never answer that prompt for existing preservation media.

At the tape `Boot`/`:` prompt, perform the licensed guest interaction from the
Open SIMH guide. The critical layout commands are reproduced so the resulting
topology cannot drift:

```text
: tm(0,3)
file sys size: 5000
file system: hp(0,0)

: tm(0,4)
Tape? tm(0,5)
Disk? hp(0,0)
[press return at the final warning]

: hp(0,0)hptmunix
# STTY -LCASE NL0 CR0
# cp hptmunix unix
# rm hphtunix rphtunix rptmunix
# cd /dev
# /etc/mknod rp0 b 6 0
# /etc/mknod swap b 6 1
# /etc/mknod rp3 b 6 15
# /etc/mknod rrp0 c 14 0
# /etc/mknod rrp3 c 14 15
# chmod go-w rp0 swap rp3 rrp0 rrp3
# make tm
# cd /
# etc/mkfs /dev/rp3 322278
# icheck /dev/rp3
# dd if=/dev/nrmt0 of=/dev/null bs=20b files=6
# restor rf /dev/rmt0 /dev/rp3
[press return at the final warning]
# /etc/mount /dev/rp3 /usr
# dd if=/usr/mdec/hpuboot of=/dev/rp0 count=1
# sync
# sync
# sync
# sync
```

Confirm `icheck` reports no missing blocks. Escape with Ctrl-E and `quit`. Do not
import while SIMH is running. The tape is input only and is never imported.

## Import and qualify — HUMAN_REQUIRED

Import is all-or-nothing, refuses partial sets and overwrite, records a SHA-256
for each disk, and makes both golden disks mode 0440:

```sh
sudo python3 scripts/utm.py golden import unix-v7-pdp11 "$STAGING"
sudo ls -l /srv/unix-time-machine/golden/unix-v7-pdp11
sudo cat /srv/unix-time-machine/golden/unix-v7-pdp11/metadata.json
```

For the first disposable boot:

```sh
python3 scripts/utm.py session prepare unix-v7-pdp11 --session-id qualification-1
python3 scripts/utm.py system start unix-v7-pdp11 --session-id qualification-1
```

At the SIMH prompt type `boot`; at `Boot`/`:` type `hp(0,0)unix`; press Ctrl-D
from single-user mode to enter multi-user mode. In another terminal:

```sh
python3 scripts/utm.py system ready unix-v7-pdp11 --session-id qualification-1 --timeout 120
```

Inside V7 run `sync` four times, Ctrl-E, then `quit`. Confirm:

```sh
python3 scripts/utm.py system status unix-v7-pdp11 --session-id qualification-1
```

Prepare and run a fresh second session identically:

```sh
python3 scripts/utm.py session prepare unix-v7-pdp11 --session-id qualification-2
python3 scripts/utm.py system start unix-v7-pdp11 --session-id qualification-2
python3 scripts/utm.py system ready unix-v7-pdp11 --session-id qualification-2 --timeout 120
```

### PASS criteria

- Golden creation: both RP06 staging files exist after a synced clean stop;
  atomic import succeeds once; both golden files are 0440; metadata contains a
  SHA-256 for `root/rp0.dsk` and `usr/rp1.dsk`; neither golden is ever attached.
- First disposable boot: the session contains both writable copies, runtime.ini
  attaches only those copies, `hp(0,0)unix` boots, `/usr` is mounted from RP1,
  filesystem checks show no errors, and the expected `login:` state is observed.
- Clean stop: four `sync` commands complete, SIMH is exited via Ctrl-E/`quit`,
  status is `STOPPED`, and both golden hashes remain identical to metadata.
- Second disposable boot: a newly prepared, distinct session again contains
  both disks, reaches `login:`, has `/usr` mounted and intact, stops cleanly, and
  leaves both golden hashes unchanged.

Until those observations occur on the qualification VM, do not claim golden
creation, V7 boot/login, filesystem integrity, repeatability, or M1 completion.
