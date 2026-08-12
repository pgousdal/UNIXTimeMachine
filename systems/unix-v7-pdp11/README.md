# UNIX V7 / PDP-11/70 (M1)

Status: **IMPLEMENTED / AWAITING HISTORICAL-SYSTEM QUALIFICATION**.

## Canonical definition

The runtime is a PDP-11/70 with 2 MiB, an RH70-class MASSBUS attachment as
represented by Open SIMH's `RP` device, and two RP06 units. RP0 contains V7 root
on `hp(0,0)` and swap on its partition 1. RP1 contains `/usr` on its partition 7;
the restored V7 name for that device is `/dev/rp3` (block major 6, minor 15),
despite the host emulator unit being RP1. Boot is from RP0, followed at the boot
prompt by `hp(0,0)unix`. Both disks remain required at runtime.

This is Model B. Installation and runtime are deliberately distinct phases. The
tape bootstrap and standalone programs run on the cited Open SIMH procedure's
PDP-11/45 with 256 KiB. They restore the root dump to RP0 and the `/usr` dump to
RP1. After a clean stop, the same two disk images are restarted on the normal
PDP-11/70 with 2 MiB and the installed system is verified before golden import.
A single RP06 has unused partitions and could be repartitioned
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
- Open SIMH, *Installing and Using Research Unix Version 7*, version 3.2 guide:
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

## Why installation uses two hardware phases

The original TUHS setup document permits the distribution tape on either a
PDP-11/45 or PDP-11/70. It specifies a TU10/TM11 as `tm`, RP04/5/6 as `hp`, and
the commands `tm(0,3)` and `tm(0,4)`. It does not require 2 MiB during standalone
bootstrap. Open SIMH's PDP-11 documentation gives the 11/45 a 256 KiB maximum
and the 11/70 a 4 MiB maximum; its simulator starts with 256 KiB. The Open SIMH
V7 procedure tested with the Keith Bostic records is more specific: it installs
on an 11/45, directly `boot tm0`, runs `tm(0,3)`, completes both RP06 images,
stops cleanly, and only then creates an 11/70/2 MiB normal-boot configuration.

The prior M1 staging file incorrectly used the later normal-runtime CPU and
memory during the earlier standalone phase. The real host reached the second
stage `Boot` prompt but `tm(0,3)` then failed with `Can't load 0 files` and a
trap. That establishes the staging mismatch as the actionable cause for this
qualification path; it does not prove that every real PDP-11/70 is incapable of
installing V7. The corrected contract follows the documented Open SIMH phase
boundary exactly. Qualification remains pending until it is rerun on the VM.

The May 2024 tape correction adds the final logical/physical end marker. It does
not add a leading file, renumber the seven source tape files, change `tm(0,3)`,
or require manual tape repositioning. The current guide identifies the corrected
SHA-1 above, reports the same file indices, and shows `boot tm0` immediately
followed by a working `tm(0,3)`. Open SIMH's built-in TM boot ROM therefore
performs the required initial positioning. Do not issue `rewind`, `space`, or
substitute `ht`: the attached simulator device is TM0, a TU10/TM11-class tape.
The pinned v3.12-3 `pdp11_tm.c` identifies this device as TM11/TU10; `tm_boot`
rewinds TM0 and its default second-block bootstrap spaces one record before
reading. The old first-block mode is available only as `boot -o`, and is neither
used nor required by the cited successful V7 procedure.

Two RP06 units on Open SIMH's `RP` device are sufficient. V7's standalone name
for RP04/5/6 remains `hp`; no additional RH controller declaration or alternate
SIMH controller name is required. `RP0`/`RP1` are simulator unit names, while
`hp(0,0)` is V7 standalone syntax.

## Create and install the two staging disks — HUMAN_REQUIRED

Choose a new staging directory outside `/srv/unix-time-machine/media` and
`/srv/unix-time-machine/golden`; it must not already exist:

```sh
STAGING=/srv/unix-time-machine/sessions/install-unix-v7-pdp11
python3 scripts/utm.py install prepare unix-v7-pdp11 "$STAGING"
/opt/unix-time-machine/simh/v3.12-3/pdp11 "$STAGING/install-bootstrap.ini"
```

The helper generates both `install-bootstrap.ini` (11/45, 256 KiB, TM0 attached
read-only, boot TM0) and `install-runtime.ini` (11/70, 2 MiB, tape disabled,
boot RP0). Both configurations attach exactly the same staging `rp0.dsk` and
`rp1.dsk`; both disable networking. SIMH creates the disks on their first
bootstrap attachment.
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

Success for the first command means `tm(0,3)` prompts for `file sys size:`. Enter
`5000`; at `file system:` enter `hp(0,0)`. It must then report `isize = 1600`,
`m/n = 3 500`, `Exit called`, and return to `Boot`/`:`. If instead it says
`Can't load`, traps, or returns to `sim>`, stop: retain the staging directory and
`install-bootstrap-console.log`, record `show cpu`, `show tm`, and `show rp`, and
do not import a golden.

Confirm `icheck` reports no missing blocks. After all four final `sync` commands,
escape with Ctrl-E and `quit`. Do not import yet and never run both phase files
at once. Start a fresh SIMH process for the explicit hardware transition:

```sh
/opt/unix-time-machine/simh/v3.12-3/pdp11 "$STAGING/install-runtime.ini"
```

This phase keeps both RP06 files but changes to the normal PDP-11/70 with 2 MiB;
the tape is disabled. At `Boot`/`:` type `hp(0,0)unix`. Expect approximately
`mem = 2020544` followed by `#`. Press Ctrl-D, log in as `root` with password
`root`, verify `/usr` is mounted from the second RP06 and run filesystem checks.
Run `sync` four times, Ctrl-E, and `quit`. The exact observed memory value may
vary slightly with the installed kernel, but it must reflect the 2 MiB runtime,
not the 11/45 bootstrap. The tape is input only and is never imported.

## Import and qualify — HUMAN_REQUIRED

Only after the installed system has booted successfully from RP0 under
`install-runtime.ini`, `/usr` from RP1 has been checked, and the guest has been
cleanly synced and stopped may it be imported. Import is all-or-nothing, refuses
partial sets and overwrite, records a SHA-256 for each disk, and makes both
golden disks mode 0440:

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
