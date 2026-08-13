# 4.3BSD on a VAX-11/780 (M3)

State: **IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION**. Nothing below is a
claim of successful operation on the Debian 13 qualification host.

## Preserved `m3-qualification-1` evidence

The disposable golden boot, readiness, ACTIVE/root login, filesystem checks,
and repeated detach/reattach all passed. After four `sync` commands,
`shutdown -h now` printed `syncing disks... done`, `HALT`, `Infinite loop ...`,
and a live `sim>` prompt. This established that 4.3BSD halt returns directly to
the SIMH monitor. The operator then manually entered `quit` before invoking the
broker stop path. The emulator exited 0 while the broker was still ACTIVE, so
the broker correctly recorded `ACTIVE -> FAILED` with `emulator exited
unexpectedly (0)`.

Retain this as failed qualification evidence: the manual quit was outside
broker control and cannot prove the broker-controlled shutdown/reset/release
path. It does not make M3 complete. The profile now permits a fresh live
post-readiness `sim>` marker to record monitor-already-active state. An attested
broker stop consumes that state, skips Ctrl-E, sends `quit`, and waits for exit.
Transcript history is never consulted as proof, and an unsolicited exit remains
a failure.

## First M3 real-host qualification finding

The first Debian 13 run with pinned Open SIMH v3.12-3 reached the 4.3BSD kernel,
identified `ra0`, `ra1`, and `ts0`, and changed root to `ra0a`. It then failed
with hard errors on `ra0a`/`ra0b` and `panic: hard IO err in swap`. SIMH had
reported `RQ: unit is read only` when the generated bootstrap configuration
attached the canonical, deliberately mode-0440 miniroot directly as `rq0`.
The miniroot environment uses `ra0`, including swap, so read-only attachment is
not a valid installation transport.

`install prepare` now keeps the preserved object unchanged and creates an
operator-owned, mode-0640 `bootstrap-miniroot.dsk` in the new staging directory.
It uses an exclusive copy-on-write reflink when the filesystem supports one and
otherwise an exclusive full copy. `install.json` records the method, canonical
source path and SHA-256, and initial copy SHA-256. The bootstrap configuration
attaches this scratch file as `rq0`; `rq1` remains the new `rq0.dsk` installation
target. Existing staging directories are refused, and only manifest-declared
prepared disks are eligible for golden import, so the bootstrap scratch image
is never published.

RA81-sized pre-expansion is not required. Inspection and reproduction used the
repository-pinned source commit and an exactly 2,099,200-byte writable file.
Open SIMH attached it as a write-enabled RA81 while retaining its original host
size. In v3.12-3, RQ capacity comes from the selected RA81 geometry (891,072
512-byte blocks), reads beyond host EOF are zero-filled, and ordinary writes
seek/write the backing file, extending it only as needed. Preparation therefore
does not inflate or sparsely extend the copy; its initial SHA-256 stays equal to
the preserved source SHA-256.

## Historical profile

The exhibit uses Open SIMH `vax780`, an 8 MiB VAX-11/780, a UDA50 with one
RA81, and a TS11 during installation. The simulator manual identifies these
devices and 8 MiB as its default VAX-11/780 memory. The installation sequence
is the stock-April-1986 4.3BSD procedure adapted to SIMH by the Computer
History Wiki. UDA50/RA81 is a repository/operator convention chosen because
that tested procedure and the distribution's `fstab.ra81` agree; it is not a
claim about a unique canonical Berkeley installation.

Networking is off: XU/XUB and DZ are disabled, no TCP console is configured,
and provisioning builds `vax780` with `NONETWORK=1` from the same pinned Open
SIMH v3.12-3 commit as PDP-11.

Sources:

- Berkeley, *Installing and Operating 4.3BSD on the VAX* (April 1986):
  https://bitsavers.org/pdf/usenix/Usenix_BSD_Manuals/4.3_1st_printing_198611/SMM_Unix_System_Managers_Manual_4.3BSD_198604.pdf
- Open SIMH VAX-11/780 simulator manual:
  https://simh.trailing-edge.com/pdf/vax780_doc.pdf
- Reproducible stock 4.3BSD/SIMH installation report:
  https://gunkies.org/wiki/Installing_4.3_BSD_on_SIMH
- Original 4.3BSD `shutdown(8)` manual:
  https://www.retro11.de/ouxr/43bsd/usr/man/cat8/shutdown.0.html
- pinned runtime source: https://github.com/open-simh/simh/tree/v3.12-3

## External media contract

### Reproducible preparation

Obtain these nine stock components from the TUHS
[`Archive/Distributions/UCB/4.3BSD/`](https://www.tuhs.org/Archive/Distributions/UCB/4.3BSD/)
directory and place them, with these exact names, in one operator-controlled
source directory:

```text
stand.gz
miniroot.gz
rootdump.gz
srcsys.tar.gz
usr.tar.gz
vfont.tar.gz
src.tar.gz
new.tar.gz
ingres.tar.gz
```

The repository does not fetch or bundle any of them. Do not decompress them
manually. Optionally put exactly one `boot42` (already decoded) or `boot42.uue`
or `boot42.uu` (original uuencode text) in that directory. The trustworthy
documented route for the latter is the Computer History Wiki
[`Boot42`](https://gunkies.org/wiki/Boot42) page, which identifies it as the
4.2BSD bootstrap used for this SIMH procedure and publishes the original
`begin 700 boot42` representation. The tool never contacts that page or a
mirror. Because neither route has an authoritative canonical digest here, the
operator must retain acquisition evidence and assess trust locally.

Prepare into a new, explicit destination (the destination must not already
exist and may not be inside the source directory):

```sh
python3 scripts/utm.py media prepare-43bsd SOURCE_DIR DEST_DIR
```

The command validates every gzip stream, losslessly emits `miniroot.gz` as
`43bsd-miniroot.dsk`, constructs `43bsd-dist.tap`, and decodes or copies
`boot42` when supplied. It never changes source files. `metadata.json` records
deterministic source/output sizes, SHA-256 values, filenames, and transformation
provenance. Outputs remain UNPINNED: these locally observed hashes document the
operation but do not authenticate historical bytes.

The tape writer reproduces the published 4.2/4.3BSD
[`mkdisttap.pl`](https://gunkies.org/wiki/Mkdisttap.pl#4.2_&_4.3_BSD): each
record is a little-endian 32-bit length, a block padded with zero bytes, and the
same trailing length; a zero 32-bit tape mark follows every file and a second
zero mark terminates the tape. The exact file order and block sizes are:

| tape file | decompressed source | block size |
|---:|---|---:|
| 1 | `stand.gz` | 512 |
| 2 | `miniroot.gz` | 10240 |
| 3 | `rootdump.gz` | 10240 |
| 4 | `srcsys.tar.gz` | 10240 |
| 5 | `usr.tar.gz` | 10240 |
| 6 | `vfont.tar.gz` | 10240 |
| 7 | `src.tar.gz` | 10240 |
| 8 | `new.tar.gz` | 10240 |
| 9 | `ingres.tar.gz` | 10240 |

This corrects the earlier prose order: `srcsys` precedes `usr`, matching both
the cited constructor and the installation sequence (`mt fsf 3` extracts the
kernel sources, then the next tape file supplies `/usr`).

Place exactly one accepted filename for each item in
`/srv/unix-time-machine/media/43bsd-vax/`:

| logical item | accepted filename(s) | status |
|---|---|---|
| SIMH distribution tape | `43bsd-dist.tap` or `43.tap` | required, UNPINNED |
| raw RA81 miniroot image | `43bsd-miniroot.dsk` or `miniroot` | required, UNPINNED |
| compatible standalone loader | `boot42` | required, UNPINNED |

No canonical size or hash is asserted. `media verify` reports SHA-256 but **does not
authenticate** these files. The tape must be an operator-created SIMH tape with
stand, miniroot, rootdump, srcsys, usr, vfont, src, new, and ingres in the order
documented by the cited installation report. That ordering is a requirement of
this operator convention; retain the original archive objects, acquisition
source, license basis, conversion commands, and resulting hashes in the
qualification record. Nothing downloads or constructs copyrighted media.

## Human installation

On the Debian 13 qualification host, from the repository checkout, use a new
operator staging path and the canonical media path (the latter must not already
exist):

```sh
python3 scripts/utm.py media prepare-43bsd /path/to/operator-obtained/4.3BSD /tmp/43bsd-vax-media
sudo mv /tmp/43bsd-vax-media /srv/unix-time-machine/media/43bsd-vax
sudo chown -R root:unix-time-machine /srv/unix-time-machine/media/43bsd-vax
sudo chmod 0750 /srv/unix-time-machine/media/43bsd-vax
sudo chmod 0440 /srv/unix-time-machine/media/43bsd-vax/43bsd-dist.tap /srv/unix-time-machine/media/43bsd-vax/43bsd-miniroot.dsk /srv/unix-time-machine/media/43bsd-vax/boot42 /srv/unix-time-machine/media/43bsd-vax/metadata.json
python3 scripts/utm.py media verify 43bsd-vax
python3 scripts/utm.py install prepare 43bsd-vax /srv/unix-time-machine/staging/43bsd-vax-QUAL --allow-unpinned
/opt/unix-time-machine/simh/v3.12-3/vax780 /srv/unix-time-machine/staging/43bsd-vax-QUAL/install-bootstrap.ini
```

Before preparation, the qualification staging path must not exist. Afterwards
its installation-relevant layout is:

```text
43bsd-vax-QUAL/
├── bootstrap-miniroot.dsk       # mutable rq0 bootstrap scratch
├── install-bootstrap.ini        # rq0=scratch, rq1=rq0.dsk
├── install-runtime.ini          # rq0=rq0.dsk
└── install.json                 # bootstrap copy/hash provenance
```

SIMH creates `rq0.dsk` as the new target when it processes the bootstrap
configuration. Console log files appear when their corresponding configuration
runs. The canonical media directory and its ownership/modes are not changed.

The `chmod` command intentionally fails if `boot42` was not supplied, stopping
the sequence before verification. If `/tmp/43bsd-vax-media` exists from an
earlier attempt, inspect and move it aside; the preparation command will not
overwrite it.

Then, after recording all provenance and hashes, continue at the miniroot
console. The equivalent final three host commands above are retained here for
orientation:

```sh
python3 scripts/utm.py media verify 43bsd-vax
python3 scripts/utm.py install prepare 43bsd-vax /srv/unix-time-machine/staging/43bsd-vax-QUAL --allow-unpinned
/opt/unix-time-machine/simh/v3.12-3/vax780 /srv/unix-time-machine/staging/43bsd-vax-QUAL/install-bootstrap.ini
```

At the miniroot `#` prompt perform the historically reported first phase:

```text
cd /dev
./MAKEDEV ra1
cd /
disk=ra1 type=ra81 tape=ts xtr
sync
sync
sync
```

Enter the monitor with Ctrl-E only after the syncs, confirm a fresh `sim>`
prompt, then `quit`. Run `install-runtime.ini`. At `#`:

```text
disk=ra
name=ra0h;type=ra81
cd /dev
sh ./MAKEDEV ts0;sync
cd /
newfs $name $type
mount /dev/$name /usr
cd /usr
mkdir sys
cd sys
mt rew
mt fsf 3
tar xpbf 20 /dev/rmt12
cd ..
mt fsf
tar xpbf 20 /dev/rmt12
cd /
chmod 755 / /usr /usr/sys
rm -rf sys
ln -s /usr/sys sys
umount /dev/$name
fsck /dev/r$name
cd /etc
cp fstab.ra81 fstab
newfs ra0g ra81
sync
reboot
```

These commands are historically sourced but still HUMAN_REQUIRED and
unqualified here. Boot the runtime configuration again to reach multi-user
`login:`. Confirm `real mem = 8388608`, `ra0`, `mount`, and `df`; disable guest
network daemons in the staged guest before publication even though no emulated
network device exists. Installation tapes and miniroot are never imported.

Publish only the complete `rq0.dsk`:

```sh
sudo python3 scripts/utm.py golden import 43bsd-vax /srv/unix-time-machine/staging/43bsd-vax-QUAL
```

The existing atomic, exclusive, root-owned 0440 golden publication path hashes
the disk and disposable sessions copy it.

## Runtime, readiness, and shutdown

The broker renders the manifest profile and retains the qualified controlling
PTY. Attach, type `run 2`, and accept `ra(0,0)vmunix` at `Boot`. Readiness is the
console `login:` prompt—not emulator start—and becomes armed on first attach.

For a multi-user guest, log in as root and run `/etc/shutdown -h now`. The
original manual says `-h` executes `halt`, while omitting `-n` retains normal
sync. Wait for console evidence that shutdown/halt has completed. Only then may
the operator attest with `broker stop SESSION --guest-synced`; that flag means
the documented 4.3BSD shutdown was observed, not merely that `sync` was typed.
For this profile the broker recognizes the fresh `sim>` emitted on the live PTY
by 4.3BSD halt. After the operator detaches and submits the attested stop, it
skips Ctrl-E, sends `quit` only from that confirmed monitor state, and requires
emulator exit. If no fresh monitor evidence exists it retains the generic
Ctrl-E -> fresh `sim>` -> `quit` fallback. Transcript history is not evidence.
Uncertainty preserves workspace, transcript, and audit.

## Debian 13 qualification gate

Record operator, UTC times, host release, repository commit, and every command.

1. `make provision` twice; record `vax780` version/provenance.
2. Prepare the operator-obtained components with `media prepare-43bsd`; retain
   its metadata with the acquisition evidence.
3. Run `utm.py doctor`, `catalog`, and `media verify 43bsd-vax`; record all
   locally observed SHA-256 values.
4. Prepare a new staging directory with `--allow-unpinned`.
5. Perform both manual installation phases above.
6. Boot staging under `install-runtime.ini`; verify 8 MiB/VAX identity and RA81.
7. Reach console `login:` and verify expected `/`, `/usr`, and `/a`/home layout
   using `mount` and `df` (record actual distribution layout).
8. Run `/etc/shutdown -h now`, observe its live `sim>` prompt, then enter `quit`
   for this installation-only run.
9. Import the one-disk golden and record metadata plus independent hashes.
10. Request broker session #1; attach, `run 2`, reach readiness, log in, verify
    filesystems, detach (Ctrl-]), reattach, and detach again.
11. Perform `/etc/shutdown -h now`; after observed halt run broker stop with
    `--guest-synced`. Do not type `quit` manually. Verify the broker recognizes
    monitor-already-active, sends no redundant Ctrl-E, then exits, resets, and releases.
12. Verify golden hash unchanged.
13. Request a completely fresh session #2 and repeat boot, readiness, login,
    filesystem checks, clean shutdown, monitor exit, reset/release, and hash check.
14. Exercise one safe failure (withhold shutdown attestation or use a bounded
    test where monitor confirmation is absent); verify evidence/workspace remains
    and no forced kill occurs. Recover only under the documented recovery path.
15. Archive console transcripts, supervisor diagnostics, broker audit JSONL,
    media report, golden metadata/hashes, and qualification notes outside Git.

Only after reviewing that evidence may ROADMAP state COMPLETE.

For the fresh broker rerun using the already imported golden:

```sh
python3 scripts/utm.py broker request 43bsd-vax --session-id m3-qualification-2
python3 scripts/utm.py broker attach m3-qualification-2
python3 scripts/utm.py broker attach m3-qualification-2
python3 scripts/utm.py broker status m3-qualification-2
python3 scripts/utm.py broker stop m3-qualification-2 --guest-synced
python3 scripts/utm.py broker status m3-qualification-2
sha256sum /srv/unix-time-machine/golden/43bsd-vax/rq0.dsk
```

Inside the attachment, boot as documented, verify readiness/login/mounts,
exercise detach/reattach, run four `sync` commands, then `/etc/shutdown -h now`.
Wait for the fresh `sim>` and detach with Ctrl-]; do not type `quit`. Run the
broker stop command only afterward and archive its transcript, supervisor log,
audit, status, and golden hash.

For the next fresh qualification attempt, use this exact new staging identity
(after confirming it does not exist):

```sh
test ! -e /srv/unix-time-machine/staging/install-43bsd-vax-2
python3 scripts/utm.py media verify 43bsd-vax
python3 scripts/utm.py install prepare 43bsd-vax /srv/unix-time-machine/staging/install-43bsd-vax-2 --allow-unpinned
sha256sum /srv/unix-time-machine/media/43bsd-vax/43bsd-miniroot.dsk /srv/unix-time-machine/staging/install-43bsd-vax-2/bootstrap-miniroot.dsk
stat -c '%U:%G %a %s %n' /srv/unix-time-machine/media/43bsd-vax/43bsd-miniroot.dsk /srv/unix-time-machine/staging/install-43bsd-vax-2/bootstrap-miniroot.dsk
python3 -m json.tool /srv/unix-time-machine/staging/install-43bsd-vax-2/install.json
/opt/unix-time-machine/simh/v3.12-3/vax780 /srv/unix-time-machine/staging/install-43bsd-vax-2/install-bootstrap.ini
```

Continue with the two documented guest phases, using
`install-runtime.ini` from the same staging directory. After the runtime boot,
filesystem checks, and clean shutdown succeed, publish only the declared target:

```sh
sudo python3 scripts/utm.py golden import 43bsd-vax /srv/unix-time-machine/staging/install-43bsd-vax-2
```

## Explicit unresolved assumptions

No canonical hashes/sizes for the archive-derived artifacts are claimed. The
exact provenance and correctness of an operator's `boot42`, miniroot conversion,
and SIMH tape construction remain qualification inputs. The documented commands
have not yet been executed with pinned v3.12-3 on the target Debian 13 host.
