# AMIX 2.1 / Amiga 3000 — M4 qualification contract

M4 is incomplete. M4.0 defines historical/media and backend architecture.
M4.1 is **COMPLETE**: Debian 13 FS-UAE provisioning and the non-AMIX hardware
substrate passed real-host qualification. M4.2 is **COMPLETE**: installation,
first boot, root/filesystem/swap checks, clean shutdown, golden publication,
and a pristine disposable-session copy were qualified. M4.3 now implements the
graphical FS-UAE session runtime; real launch through `utm.py system start`
remains pending. There is not yet a qualified AMIX serial/getty broker console.

## Evidence classification

**CONFIRMED — primary documentation.** Commodore's *Amiga UNIX Version 2.1
Addendum* requires a 68020 with 68851 or a 68030, a 68881/68882 FPU, at least
4 MiB contiguous Fast RAM, and supported SCSI/RigidDiskBlock storage. The
Amiga 3000 is an intended machine. Commodore's *Installing Amiga UNIX*
documents the boot/root-floppy, installation-tape, installed-disk, and
post-install configuration workflow. Sources:

- Commodore, *Installing Amiga UNIX* (1990), Internet Archive item
  `commodore-amiga-unix-system-v-release-4-installing-amiga-unix`.
- Commodore, *Amiga UNIX Version 2.1 Addendum*, preserved at
  `https://www.amigaunix.com/lib/exe/fetch.php/manuals%3Av2releasenotes.pdf`.

**PLANNED.** The exhibit target is base AMIX 2.1 followed by the official 2.1
patch. Patch level 2a and a 2.1c kernel are the intended result, not a verified
repository claim. The initial qualification machine is an A3000/A3000UX-
compatible 68030 with MMU, 68882-compatible FPU, 2 MiB Chip RAM, 16 MiB Fast
RAM, ECS/A3000 chipset, JIT disabled, tape at SCSI ID 4, and an RDB system
hardfile at SCSI ID 6. The IDs, 16 MiB target, multi-member emulator tape
representation, and later FS-UAE operational guidance rely on specialist AMIX
preservation experience and must be qualified; they are not elevated to
primary-source facts here.

**HUMAN_REQUIRED / UNQUALIFIED.** An operator must lawfully supply and identify
the two base floppies, ordered installation-tape representation, official patch
floppy, and compatible A3000 Kickstart ROM, plus a ROM key only when that ROM
representation requires one. The repository assigns no filenames, labels,
hashes, tape member names/order, or ROM identity. `media verify` therefore
reports these logical artifacts missing until a later explicit-path workflow is
implemented. Availability and redistribution rights are uncertain.

## Preservation contract

```text
external immutable source media
        -> writable private installation staging
        -> installed AMIX hardfile
        -> immutable golden
        -> disposable broker session copy
```

Installation and patch floppies must be copied into private writable staging
before use. Tape and ROM inputs must be attached with enforced read-only
semantics; if a future backend cannot guarantee that, it must use private
staging copies. Source hashes are recorded as observed UNPINNED provenance, not
authenticity claims.

The golden contains only the installed system hardfile and canonical golden
metadata. The generic prepared-disk contract selects the exact staging file
`base-amix-2.1-installation-staging.hdf`, publishes it as `amix-system.hdf`,
and does not copy installation or patch floppies, tape members or containers,
ROMs, ROM keys, or rendered installation configuration. Publication retains
the generic atomic, read-only, root:`unix-time-machine` policy; sessions remain
copy-on-session. No AMIX-specific import bypass exists.

Guest networking is disabled. No TCP listener or public access is part of M4.

## Future console design

The planned authoritative runtime console is an AMIX login service on the
emulated built-in serial port, connected to a broker-owned local PTY. Emulator
stdout/stderr would be separate diagnostics; an FS-UAE graphical window would
not be the broker console. This is architecture, not implemented behavior.

No serial device name, getty/inittab entry, baud rate, root-login policy,
shutdown command, or halt marker is specified. Each must come from the installed
system and real-host evidence.

## Qualification gates

- **M4.1 — COMPLETE:** Debian 13 amd64
  `fs-uae=3.1.66-2+b1` from Trixie `main` is pinned. The signed archive index
  identifies `pool/main/f/fs-uae/fs-uae_3.1.66-2+b1_amd64.deb` with SHA-256
  `5f703e361d242a99da46454a0b21aafed6010e4153682f1aeed9f59e5cd3d9e4`.
  Provisioning records installed dependency versions, apt policy, version
  output, and executable hash. The launcher and network helpers are absent.
  Real-host qualification confirmed A3000 startup, MMU/FPU, memory, RDB, tape,
  ROM loading, local serial PTY attachment, controlled exit, and local display.
- **M4.2 — COMPLETE:** observed
  media inventory, preservation-safe staging, and the generic golden-import
  contract are implemented. A real installation passed hard-disk first boot,
  root login, filesystem/swap verification, and clean System V shutdown. The
  installed HDF also passed RDB/PART structure and bootblock checksum checks.
  The installed HDF was imported through the generic mechanism, the immutable
  golden verified byte-identical, and a pristine disposable session verified
  byte-identical before first launch.
- **M4.3 — IMPLEMENTED / REAL-HOST SESSION LAUNCH PENDING:** generic runtime
  rendering now selects the writable disposable RDB, protected operator ROM/key,
  and qualified graphical FS-UAE hardware profile. It does not claim guest
  readiness from emulator process state.
- **Later gates:** official patch identity; exact serial device, getty/inittab,
  baud and privileged-login behavior; broker attach/detach, shutdown driver,
  halt marker/behavior, readiness, and full real-host qualification.

## M4.1 source-backed substrate

The derived template `m41-probe.fs-uae.in` is based on FS-UAE 3.1.66 source
and upstream option documentation, not an AMIX configuration copied from an
archive. Source behavior establishes the following implementation capability:

- `A3000` selects the model and a 68030; explicit `cpu`, `mmu`, and `fpu`
  select 68030/68030/68882.
- `chip_memory` and `motherboard_ram` express KiB values; the target is
  2048 KiB and 16384 KiB.
- `hard_drive_0_type = rdb` forces an empty HDF into RDB mode. The disposable
  probe HDF deliberately has no final geometry or partition table.
- `scsi6` is passed as the hardfile controller/unit selector.
- The low-level `uaehf` parser supports a read-only tape device, SCSI
  controller selector `scsi4`, a directory/archive representation, and an
  optional `index.tape` ordering file. M4.1 creates only a harmless synthetic
  member and index.
- `serial_port` accepts a Unix device path. The qualifier allocates a local
  PTY and supplies its slave path; it never supplies `tcp://`.

These are source-level findings. They do not prove the Debian binary accepts
the rendered configuration, starts successfully, exposes devices to AMIX, or
transfers serial bytes. The qualifier fails unless required diagnostics are
observed. Bidirectional serial traffic remains SKIP without a guest serial
driver, and AMIX getty work remains M4.3.

The first Debian 13 run exposed a qualifier defect, not a topology failure:
FS-UAE's stdout/stderr was sparse while detailed UAE evidence was written to
the default mutable user cache. The reconciled qualifier sets `logs_dir` to a
new, empty per-run directory beneath the probe workspace. It preserves
`fs-uae-stdout.log`, `fs-uae-stderr.log`, `fs-uae.log.txt`, the exact run
configuration, and `qualification.json` together. The detailed log must have
been created after that run's recorded launch boundary; neither a prior run nor
rendered config text can satisfy runtime evidence.

Pinned 3.1.66 source accepts `network_card = 0` as no card. The former value
`none` was invalid and produced `WARNING: Unrecognized network card`; that
warning is now a qualification failure. Runtime validation requires the UAE
log to show the A3000 match, CPU/FPU/MMU/JIT values, translated 2 MiB Chip and
16 MiB A3000 memory values, mainboard SCSI initialization, the exact probe RDB
opened as HD unit 6, tape unit 4 and its exact index, and the allocated serial
PTY actually opened. Clean SDL shutdown is also required.

The observed external Amiga Forever ROM begins with `AMIROMTYPE1`, and the
generated run configuration explicitly supplies the protected key path. The
runtime log records the exact ROM path being read, its observed SHA-1, and
`Unknown ROM '<path>' loaded`; run-specific stdout records a 524288-byte
Kickstart load. Together these attest successful loading of the encrypted
source with the configured key. They do not attest an explicit key-open or
decrypt message, because FS-UAE emitted neither, and they do not establish an
internal ROM identity. The qualifier records the literal `Unknown ROM`
classification and runtime SHA-1 only as observations.

For the RDB probe, successful opening requires all observed pinned-emulator
forms in the current run: explicit RDB type, `rdb mode: 1`, the literal
`hfd open:` line for the exact probe path, and the corresponding `HDF '<path>'
opened, size=<expected>K mode=3 empty=0` line. The independent A3000 mainboard
SCSI HD-unit-6 predicate remains required.

The Debian binary links SDL/OpenGL/X11 libraries. Xvfb `:99` with `-nolisten
tcp` and llvmpipe started it successfully on the headless qualification host,
with no new TCP listener. This is an observed local-only display candidate,
not a universal FS-UAE requirement. M4.1 therefore does not add Xvfb to every
host's foundation provisioning: a host with a real local X display does not
need it. Missing `DISPLAY` remains HUMAN_REQUIRED, not PASS. Install/provision
Xvfb as a qualification-host prerequisite only where that host has no local
display.

## M4.1 final real-host qualification record

The Debian 13/Trixie amd64 host passed two provisioning runs; the second
reported `changed=0`. The installed dependency and observed executable were:

- Debian package `fs-uae=3.1.66-2+b1` from Trixie `main`.
- Executable SHA-256
  `7349ac3aed9a61e81254b81d1b2bf58ea9aa5bc0bbe00fc3f9e4845beafd568d`.
- Archive package SHA-256
  `5f703e361d242a99da46454a0b21aafed6010e4153682f1aeed9f59e5cd3d9e4`.

The protected, operator-supplied inputs were observed as UNPINNED provenance,
not canonical identities:

- ROM SHA-256
  `3cd65ab48bad3238e63f4da4df59fac187ecbbc45b48fdfd78d360133113ddaf`.
- ROM-key SHA-256
  `f3b3b35593fef9a677225f559f8155e2b5d97b5bbfb2ccf24ee93738124d9a71`.

The run result recorded `configuration_accepted=true`,
`controlled_exit_code=0`, `new_tcp_listeners=[]`, and
`topology_evidence_missing=[]`. Run-scoped evidence passed for:

- A3000; 68030 CPU, 68882 FPU, 68030 MMU, and JIT disabled.
- 2 MiB Chip RAM and 16 MiB A3000 motherboard RAM.
- A3000 mainboard SCSI initialization; the disposable RDB hardfile opened on
  HD unit 6.
- SCSI tape unit 4 and the synthetic ordered tape index.
- The local serial PTY configured and opened.
- An `AMIROMTYPE1` encrypted source, exact protected key path in the generated
  configuration, exact ROM path read, and a 524288-byte Kickstart load.
- Runtime ROM SHA-1
  `864bf136c5997d9c0c9fa89ce62249364bb19859`, recorded as an observation.
- Literal FS-UAE classification `Unknown ROM`; no internal identity is claimed.
- Clean SDL shutdown.

Bidirectional serial bytes remain **SKIP** until an AMIX guest serial driver and
getty exist. No guest networking, public display, TCP serial transport, or
public listener was introduced. All earlier failed qualification workspaces
and logs remain preservation evidence.

## M4.1 reproduction procedure

On the Debian 13 amd64 qualification host:

```sh
make provision
make provision                         # must report changed=0
sudo cat /opt/unix-time-machine/fs-uae/3.1.66-2+b1/PROVENANCE
sudo install -o root -g unix-time-machine -m 0440 /lawful/path/to/a3000.rom \
  /srv/unix-time-machine/media/amix-a3000/operator-rom
sudo install -o root -g unix-time-machine -m 0440 /lawful/path/to/rom.key \
  /srv/unix-time-machine/media/amix-a3000/operator-rom-key
python3 scripts/fsuae_m41.py prepare \
  --rom /srv/unix-time-machine/media/amix-a3000/operator-rom \
  --rom-key /srv/unix-time-machine/media/amix-a3000/operator-rom-key \
  --workspace /srv/unix-time-machine/staging/amix-m41-reconciliation
DISPLAY=:99 python3 scripts/fsuae_m41.py qualify \
  --workspace /srv/unix-time-machine/staging/amix-m41-reconciliation
find /srv/unix-time-machine/staging/amix-m41-reconciliation/runs \
  -type f -printf '%M %u:%g %s %p\n'
ss -ltnp
sha256sum /srv/unix-time-machine/media/amix-a3000/operator-rom
find /srv/unix-time-machine/media /srv/unix-time-machine/golden \
  -printf '%M %u:%g %p\n'
```

The commands above reproduce the observed encrypted-ROM/Xvfb case: install the
operator key read-only at the shown operator-chosen path and ensure the already
qualified local-only Xvfb `:99` is running. For an unencrypted ROM or a real
local display, omit `--rom-key` or use the actual `DISPLAY`; neither path may be
assumed equivalent until observed. Use a new staging workspace so evidence from
the false-negative run remains intact. Review `probe.json` and every file in
the new `runs/run-*` directory. Retain every workspace on failure.

Qualification evidence distinguishes configuration acceptance, emulator
startup, logged topology, and guest-visible behavior. Device visibility to
AMIX is deferred to M4.2. No new TCP listener may appear, and a controlled
SIGTERM exit must complete.

## M4.2 operator-media and staging contract

`media inventory-amix` consumes an operator-authored JSON specification with
exactly `boot_floppy`, `root_install_floppy`, and `installation_tape` roles.
Each floppy maps an explicit protected path to the operator's non-empty source
description. The tape maps its protected directory, exact existing ordering
index, and source description. No filename is prescribed by the repository.
The command records observed paths/names, sizes and SHA-256 values as local
UNPINNED provenance under `reports/amix-a3000`; it does not authenticate or
download media.

The tape index is authoritative observed ordering. Blank, duplicate, missing,
unsafe, or unreferenced members fail closed. The index and every referenced
member must be immutable files beneath protected AMIX media storage. M4.1
qualified read-only directory tape attachment. An observed directory already
using FS-UAE's exact `index.tape` convention is referenced read-only. For any
differently named observed index/seglist, preparation preserves it unchanged
and copies the ordered members into a private read-only staging representation
with a derived `index.tape`; every copy method and source hash is recorded.

`install prepare-amix` revalidates every inventoried hash, requires an explicit
positive RDB candidate size, and creates a new operator-owned workspace beneath
the generic staging root. It makes mode-0640 private copies of both floppies,
records source/output hashes and copy methods before first boot, creates a new
sparse hardfile named `base-amix-2.1-installation-staging.hdf`, and records final
geometry/partitions as HUMAN_REQUIRED. This name is deliberately not a golden.

The generated `install.fs-uae` uses the qualified A3000/68030/MMU/68882,
2 MiB Chip/16 MiB motherboard RAM profile, JIT and networking disabled, the
operator ROM/key, private boot/root floppy set, read-only tape at SCSI ID 4,
and writable RDB disk at SCSI ID 6. `base-first-boot.fs-uae` contains the same
profile and RDB but no installation floppy or tape. Both use private detailed
logging; native display is authoritative. Neither config contains serial,
getty, patch, broker, or guest-network setup.

Failures never trigger staging cleanup. The workspace retains copies, disk,
rendered configuration, logs, screenshots, inventory linkage, and the
HUMAN_REQUIRED evidence worksheet. Preparation never creates a golden. After
qualification, the generic importer can publish only the manifest-selected RDB.

### M4.2 preparation commands

First create an operator JSON file containing the three logical-role mappings
described above. Paths and descriptions must reflect the actual protected
media. Its structure is:

```json
{
  "boot_floppy": {"path": "OPERATOR_BOOT_PATH", "source_description": "OPERATOR_DESCRIPTION"},
  "root_install_floppy": {"path": "OPERATOR_ROOT_PATH", "source_description": "OPERATOR_DESCRIPTION"},
  "installation_tape": {
    "directory": "OPERATOR_TAPE_DIRECTORY",
    "index_path": "OPERATOR_ORDERING_SOURCE",
    "source_description": "OPERATOR_DESCRIPTION"
  }
}
```

Capitalized values are required operator substitutions, not historical
filenames or canonical paths. Then run:

```sh
python3 scripts/utm.py media inventory-amix \
  /path/to/operator-authored-m42.json \
  /srv/unix-time-machine/reports/amix-a3000/m42-media.json

python3 scripts/utm.py install prepare-amix \
  /srv/unix-time-machine/reports/amix-a3000/m42-media.json \
  /srv/unix-time-machine/staging/amix-m42-base-install \
  --rom /srv/unix-time-machine/media/amix-a3000/operator-rom \
  --rom-key /srv/unix-time-machine/media/amix-a3000/operator-rom-key \
  --rdb-size-mib RDB_CANDIDATE_MIB
```

`RDB_CANDIDATE_MIB` is an explicit qualification input, not the former 450 MiB
planning value. Replace it only with the operator's documented practical
candidate. The staging path must not already exist.

### M4.2 real-host installation gate

With the already-local Xvfb `:99` running with `-nolisten tcp`, record the
listener baseline and launch the installer exactly as follows:

```sh
ss -H -ltn > /srv/unix-time-machine/staging/amix-m42-base-install/listeners-before.txt
DISPLAY=:99 /usr/bin/fs-uae \
  /srv/unix-time-machine/staging/amix-m42-base-install/install.fs-uae \
  > /srv/unix-time-machine/staging/amix-m42-base-install/fs-uae-install.stdout \
  2> /srv/unix-time-machine/staging/amix-m42-base-install/fs-uae-install.stderr
ss -H -ltn > /srv/unix-time-machine/staging/amix-m42-base-install/listeners-after.txt
```

From the native display, record screenshots and the exact observed sequence in
`installation-evidence.json`: initial boot, boot-to-root floppy transition,
language/installation selection, disk and tape detection, disk initialization,
RDB/partition and filesystem creation, package selection, every tape/member
transition, kernel/system installation, completion, and required media
ejection. No guest command or prompt text is specified until observed.

After completion, stop the emulator without inventing an AMIX shutdown claim,
then run the generated hard-disk-only configuration with the same stdout/stderr
capture pattern:

```sh
DISPLAY=:99 /usr/bin/fs-uae \
  /srv/unix-time-machine/staging/amix-m42-base-install/base-first-boot.fs-uae \
  > /srv/unix-time-machine/staging/amix-m42-base-install/fs-uae-first-boot.stdout \
  2> /srv/unix-time-machine/staging/amix-m42-base-install/fs-uae-first-boot.stderr
```

The real-host run confirmed no floppy or tape was needed for the hard-disk
boot, completed installation and first boot, reached root login, found `/`
mounted read/write and swap active on `/dev/dsk/c6d0s2`, and completed a clean
`shutdown -y -g0`. Independent checks passed the HDF's RDB, PART blocks, UNIX
bootblock checksums, and related structures. The installed HDF was imported by
the generic golden mechanism and verified byte-identical to staging; a newly
prepared session was byte-identical to golden before launch. The pristine
SHA-256 was `48d36859b1b69cf0cd56f6b846b5a4369575f3350225a60451c9d827865db918`.

Amiga Forever A3000 Kickstart 2.04 produced a persistent white-screen boot
failure under the tested FS-UAE UAE core. A3000 Kickstart 3.1 successfully
booted the exact same verified RDB/HDF. The currently qualified runtime thus
requires a compatible operator-supplied A3000 Kickstart 3.1 representation.
This is an emulator compatibility result, not a claim that AMIX cannot run
with Kickstart 2.04 on real hardware. These observations do not establish the
later patch, serial-console, or broker runtime contracts.

Before and after each emulator run, compare listening TCP sockets. After the
installation, re-hash every canonical source listed in the inventory and record
the results with:

```sh
python3 scripts/utm.py media verify-amix-inventory \
  /srv/unix-time-machine/reports/amix-a3000/m42-media.json
```

Any failure remains preserved. Golden publication is deliberately not part of
automated validation and remains this explicit operator action after this
commit:

```sh
sudo python3 scripts/utm.py golden import amix-a3000 \
  /srv/unix-time-machine/staging/amix-m42-base-install
```

That explicit publication and verification has now completed. The observed
installed-output hash is qualification evidence, not versioned source-media
identity, and is therefore not pinned in the manifest.

## M4.3 graphical runtime backend

`runtime.fs-uae.in` is the canonical repository-owned runtime template. The
generic renderer substitutes only the disposable session's `amix-system.hdf`;
it never attaches the golden. It selects A3000, 68030 CPU/MMU, 68882 FPU,
2 MiB Chip RAM, 16 MiB motherboard RAM, no JIT, no networking, and a writable
RDB hardfile using the qualified `scsi6` controller selector. The FS-UAE
front-end diagnostic that `scsi6` is not known is retained: the tested core
then initialized A3000 mainboard SCSI and attached HD unit 6 successfully.

Runtime ROM material remains under protected operator media. The established
deployment names are `operator-rom` and, when required, `operator-rom-key`.
An `AMIROMTYPE1` representation requires the key before launch; an unencrypted
representation may omit it. Rendered configuration contains paths, never ROM
or key bytes. Display selection remains an operator host concern and the
template does not prescribe Xvfb or `DISPLAY`.

`system start` retains the existing emulator lookup, deterministic renderer,
PTY process supervision, transcript, state file, and argv-list execution. In
this graphical phase the PTY captures emulator diagnostics, not an AMIX guest
console. `system status` can report emulator process state, while `system
ready` returns `HUMAN_REQUIRED`; root login remains human-verified until the
serial/getty milestone. M4.3 must not be called qualified until a real
disposable session boots through `utm.py system start`.
