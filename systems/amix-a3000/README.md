# AMIX 2.1 / Amiga 3000 — M4 design and M4.1 qualification contract

M4 is incomplete. M4.0 defines historical/media and backend architecture.
M4.1 implements a Debian 13 FS-UAE provisioning and non-AMIX hardware probe,
but awaits real-host qualification. There is no FS-UAE backend, AMIX installer,
golden, or qualified AMIX console path in this repository.

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

- **M4.1 — IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION:** Debian 13 amd64
  `fs-uae=3.1.66-2+b1` from Trixie `main` is pinned. The signed archive index
  identifies `pool/main/f/fs-uae/fs-uae_3.1.66-2+b1_amd64.deb` with SHA-256
  `5f703e361d242a99da46454a0b21aafed6010e4153682f1aeed9f59e5cd3d9e4`.
  Provisioning records installed dependency versions, apt policy, version
  output, and executable hash. The launcher and network helpers are absent.
  The probe must still qualify A3000 startup, MMU/FPU, RDB, tape, ROM, serial
  PTY, controlled exit, and display behavior on the Debian host.
- **M4.2:** observed media labels/names/hashes; tape representation and order;
  successful install; exact RDB geometry and partition layout.
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

The Debian binary links SDL/OpenGL/X11 libraries. Xvfb `:99` with llvmpipe was
observed to start it successfully on the headless qualification host, with no
new TCP listener. This is an observed local-only display candidate, not a
universal FS-UAE requirement. M4.1 therefore does not add Xvfb to every host's
foundation provisioning: a host with a real local X display does not need it,
and the corrected real-host rerun must still qualify the complete topology.
Missing `DISPLAY` remains HUMAN_REQUIRED, not PASS. Install/provision Xvfb as a
qualification-host prerequisite only where that host has no local display.

## Exact M4.1 real-host procedure

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

Qualification evidence must distinguish configuration acceptance, emulator
startup, logged topology, and guest-visible behavior. A native A3000 ROM screen
must be checked by a human. Device visibility to AMIX is deferred to M4.2. No
new TCP listener may appear. A controlled SIGTERM exit must complete. Reconcile
this document with the resulting evidence before calling M4.1 complete.
