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
