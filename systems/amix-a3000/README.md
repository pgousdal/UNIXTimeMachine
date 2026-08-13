# AMIX 2.1 / Amiga 3000 — M4.0 design contract

M4 is incomplete. M4.0 defines historical/media and backend architecture only:
there is no FS-UAE backend, runtime configuration, installer, golden, or
qualified console path in this repository.

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

- **M4.1:** exact Debian 13 FS-UAE provenance/pin; A3000 startup; MMU/FPU,
  RDB, SCSI tape, ROM, local serial PTY, and display/X behavior.
- **M4.2:** observed media labels/names/hashes; tape representation and order;
  successful install; exact RDB geometry and partition layout.
- **M4.3:** official patch procedure and resulting identity; exact serial
  device, getty/inittab, baud and privileged-login behavior; exact clean halt
  command/marker; FS-UAE behavior after halt.
- **M4.4:** real FS-UAE backend, external serial transport, readiness,
  attach/detach, shutdown driver, and preservation-safe failures.
- **M4.5:** complete real-host qualification, including two fresh disposable
  sessions and unchanged golden evidence.
