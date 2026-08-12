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
overwrite, and makes every disk group-readable but not writable. Session
preparation uses exclusive reflinks where supported and fully copied, fsynced
fallbacks otherwise. It hashes every golden before and after copying and never
publishes session metadata for a partial copy.

Open-source emulator provenance is independently pinned: the installed PDP-11
binary has a root-owned `PROVENANCE` record naming upstream, version, full
commit, source URL, source SHA-256, target, and build options. This does not
authenticate or alter operator-supplied UNIX media and must not be confused with
a historical-media verification result.
