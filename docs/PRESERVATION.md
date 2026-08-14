# Preservation Policy

Record provenance, logical name, version, source, acquisition date, size and SHA-256 where practical. Keep source media separate from normalized media, golden systems and disposable session state. Public sessions must never write to source media or golden images.

For M1, media verification is read-only. The supported tape is the exact SIMH
bitstream currently published by TUHS at
`Archive/Distributions/Research/Keith_Bostic_v7/v7.tap.gz`, identified after
decompression by size and SHA-256 in the manifest. This identifies bytes, not an
untouched physical-tape capture, legal permission, or every legitimate V7 tape
layout. Alternate distributions and earlier generated layouts are unverified;
they fail the canonical check even if named `v7.tap`.

Golden import accepts only the complete manifest disk set from a staging
directory outside `media/`, constructs and hashes it transactionally, refuses
overwrite, and publishes the directory as `root:unix-time-machine` mode 0750
with every disk and its metadata `root:unix-time-machine` mode 0440. Explicitly
enrolled operators can read golden data but cannot modify it. Session
preparation uses exclusive reflinks where supported and fully copied, fsynced
fallbacks otherwise. It hashes every golden before and after copying and never
publishes session metadata for a partial copy.

Open-source emulator provenance is independently pinned: the installed PDP-11
binary has a root-owned `PROVENANCE` record naming upstream, version, full
commit, source URL, source SHA-256, target, and build options. This does not
authenticate or alter operator-supplied UNIX media and must not be confused with
a historical-media verification result.

M2 records the complete golden hash set in each session record at preparation.
Before reset/release it hashes the immutable set again; a mismatch changes the
session to FAILED and preserves the workspace. A confirmed emulator exit is
required before disposable disks are removed. Reset deletes only the session
workspace, never `golden/`; transcript, supervisor diagnostics, audit JSONL and
the released state record remain available outside that workspace.

Partial preparation, stale PID identity, supervisor loss, emulator exit and
ambiguous teardown all retain evidence. Reconciliation reports orphan
transaction directories and failed sessions but does not remove them. Audit
events deliberately exclude terminal contents; the separate console transcript
may contain guest-entered data and must be protected under local policy.
## M3 VAX exhibit

The 4.3BSD contract deliberately leaves the operator-created SIMH tape,
miniroot image, and standalone loader unpinned. `UNPINNED` records a digest for
comparison but is not authentication. Staging requires `--allow-unpinned` so
that this boundary cannot be crossed accidentally. Golden publication accepts
only `rq0.dsk`; installation tape/miniroot/loader remain external, and sessions
receive disposable copies through the same atomic model as M1.

The repository-owned M3 preparation tool operates only on an explicit
operator-supplied source directory and a new destination outside it. It
validates and decompresses gzip inputs, reproduces the historically documented
SIMH `mkdisttap` framing/order, optionally validates and decodes the documented
`boot42` uuencode representation, and writes deterministic transformation
metadata. It neither downloads media nor assigns canonical hashes; source bytes
remain unchanged and every observed input/output hash is local provenance only.

Final M3 qualification retained that distinction. The locally observed hashes
are `26e34688d233f25754ab7b7d3bdcaccb55ff7e670e9977d29fa1afb76f5675fe`
for `43bsd-miniroot.dsk`,
`d192e5f90bf12ff390b10ae81e25799e56c8d3b3623ba3a497b5fe2841766bf9`
for `43bsd-dist.tap`, and
`a7bacc518350f4ebb1c21e7f578f91dd843ef42c26d912a1a9d227b2fac07eff`
for `boot42`; all remain UNPINNED. The published mode-0440 golden `rq0.dsk`
hash is `1b8e4e73e40a4044f2eed8e13d7f1f69d1cccd6ccfb582fa6e11735f9a77aba7`
and was unchanged after two disposable-session qualifications. Failed session
and timeout evidence remains preserved; no automatic evidence deletion was
introduced.

## M4 AMIX boundary

M4 defines this flow: external immutable boot/root and
patch floppies, an ordered installation-tape representation, and an A3000 ROM
become inputs to private installation staging; only the installed RDB hardfile
may proceed to an immutable golden and disposable session copy. Floppies must
be writable private copies during installation. Tape and ROM attachments must
be enforced read-only or replaced with private staging copies.

AMIX media are external, operator-supplied and UNPINNED. No repository evidence
authorizes canonical source-media filenames, labels, member ordering, sizes or
hashes. The implemented generic prepared-disk contract accepts only
`base-amix-2.1-installation-staging.hdf` as installed-system input and publishes
it as `amix-system.hdf`. The golden contains only that hardfile and metadata,
never installation media, ROM material, keys, or installation configuration.
Real publication completed through that generic path. The qualified golden and
its pristine pre-launch session shared SHA-256
`48d36859b1b69cf0cd56f6b846b5a4369575f3350225a60451c9d827865db918`.
Repository validation neither accesses nor republishes either real artifact.
The M4.3 renderer attaches only the writable session hardfile and references
the protected operator ROM/key by path; those proprietary bytes do not enter
the golden, session, generated metadata, or repository.
