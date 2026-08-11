# Preservation Policy

Record provenance, logical name, version, source, acquisition date, size and SHA-256 where practical. Keep source media separate from normalized media, golden systems and disposable session state. Public sessions must never write to source media or golden images.

For M1, media verification is read-only. `UNPINNED` means a SHA-256 was computed
and displayed but no trusted canonical value exists in the manifest; it is not
cryptographic verification. Operators should retain that value with their own
provenance record and propose a manifest pin only when its canonical status and
redistribution-independent identity are supportable. Never invent a hash.

The golden import rejects paths beneath `media/`, uses exclusive creation, and
makes the resulting disk group-readable but not writable. Session preparation
uses an exclusive reflink when the filesystem supports it and a fully copied,
fsynced fallback otherwise. It hashes the golden before and after copying and
never overwrites a session. Discard only the named session directory after SIMH
has stopped; the CLI intentionally has no recursive discard command in M1.
