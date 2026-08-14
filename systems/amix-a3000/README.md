# AMIX 2.1 / Amiga 3000 — M4 design and M4.1 qualification contract

M4 is incomplete. M4.0 defines historical/media and backend architecture.
M4.1 is **COMPLETE**: Debian 13 FS-UAE provisioning and the non-AMIX hardware
substrate passed real-host qualification. There is no FS-UAE backend, AMIX
golden, or qualified AMIX console path in this repository. M4.2 media inventory
and base-install staging are implemented but await a real operator-media run.

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

The future golden contains only the installed system hardfile and golden
metadata. Golden publication must reject installation and patch floppies, tape
members or containers, ROMs, ROM keys, and rendered installation configuration.
M4.0 adds no AMIX golden-import special case because no installed-disk contract
has been qualified.

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
- **M4.2 — IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION:** observed media
  inventory and base-install staging are implemented. No operator AMIX media or
  completed installation evidence is available in this repository; exact
  filenames, hashes, prompt sequence, RDB geometry, partitions, filesystems,
  and shutdown behavior remain HUMAN_REQUIRED.
- **M4.3:** official patch procedure and resulting identity; exact serial
  device, getty/inittab, baud and privileged-login behavior; exact clean halt
  command/marker; FS-UAE behavior after halt.
- **M4.4:** real FS-UAE backend, external serial transport, readiness,
  attach/detach, shutdown driver, and preservation-safe failures.
- **M4.5:** complete real-host qualification, including two fresh disposable
  sessions and unchanged golden evidence.

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
HUMAN_REQUIRED evidence worksheet. No AMIX golden is created or importable from
this manifest.

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

Confirm no floppy or tape is attached, reach native login or first-boot
configuration, and record base AMIX
2.1 identity, devices, memory, partitions, filesystems, boot partition, and
release data. Observe the minimum safe shutdown command, sync/unmount output,
stable halted marker, and whether FS-UAE remains running; these observations
are inputs to M4.3, not an implemented shutdown protocol.

Before and after each emulator run, compare listening TCP sockets. After the
installation, re-hash every canonical source listed in the inventory and record
the results with:

```sh
python3 scripts/utm.py media verify-amix-inventory \
  /srv/unix-time-machine/reports/amix-a3000/m42-media.json
```

Any failure remains preserved. M4.2 becomes COMPLETE only after
all 20 real-host gates in the task are reconciled; until then the installation
procedure and evidence remain HUMAN_REQUIRED.
