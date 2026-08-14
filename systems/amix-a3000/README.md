# AMIX 2.1 / Amiga 3000 — M4.0 design contract

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

The Debian binary links SDL/OpenGL/X11 libraries. M4.1 does not provision Xvfb:
qualification first requires an ordinary local `DISPLAY`. Absence of one is
HUMAN_REQUIRED, not PASS. If Debian qualification proves Xvfb necessary, that
dependency requires a separately evidenced change.

## Exact M4.1 real-host procedure

On the Debian 13 amd64 qualification host:

```sh
make provision
make provision                         # must report changed=0
sudo cat /opt/unix-time-machine/fs-uae/3.1.66-2+b1/PROVENANCE
sudo install -o root -g unix-time-machine -m 0440 /lawful/path/to/a3000.rom \
  /srv/unix-time-machine/media/amix-a3000/operator-rom
python3 scripts/fsuae_m41.py prepare \
  --rom /srv/unix-time-machine/media/amix-a3000/operator-rom \
  --workspace /srv/unix-time-machine/staging/amix-m41-qualification
DISPLAY=:0 python3 scripts/fsuae_m41.py qualify \
  --workspace /srv/unix-time-machine/staging/amix-m41-qualification
ss -ltnp
sha256sum /srv/unix-time-machine/media/amix-a3000/operator-rom
find /srv/unix-time-machine/media /srv/unix-time-machine/golden \
  -printf '%M %u:%g %p\n'
```

Use the actual local display value rather than assuming `:0`. If the supplied
ROM representation lawfully requires a key, install it under the same protected
media directory with a noncanonical operator-chosen name and add `--rom-key`
to `prepare`; no key name or hash is prescribed. Review `probe.json`, the
rendered configuration, `fs-uae-diagnostics.log`, and `qualification.json`.
Retain the workspace on every failure.

Qualification evidence must distinguish configuration acceptance, emulator
startup, logged topology, and guest-visible behavior. A native A3000 ROM screen
must be checked by a human. Device visibility to AMIX is deferred to M4.2. No
new TCP listener may appear. A controlled SIGTERM exit must complete. Reconcile
this document with the resulting evidence before calling M4.1 complete.
